"""Sổ đăng ký công cụ của chatbot và cổng kiểm định (kế hoạch 5.1, S6, RC-27).

Engine DB chỉ đọc chỉ là rào chắn: một phiên cố tình vẫn có thể tắt chế độ chỉ đọc. An toàn thật
dựa vào việc **không công cụ nào nhận SQL hay chuỗi truy vấn tự do từ model**. Mọi công cụ (5.2 trở
đi) đăng ký qua `ToolRegistry.register`, nơi từ chối khai báo nhận tham số kiểu đó, và được gọi qua
`ToolRegistry.call`, nơi mọi đối số do model đưa vào bị kiểm kiểu, enum, độ dài và khóa lạ trước
khi handler nhìn thấy.

Lưu ý: danh sách tên bị chặn chỉ là rào nhẹ. Chốt thật là handler luôn truyền tham số qua bind
(`:param`), cộng role Postgres chỉ-`SELECT` ở 2D.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Literal

ToolParameterKind = Literal["integer", "number", "boolean", "string", "uuid", "date"]

_KINDS = ("integer", "number", "boolean", "string", "uuid", "date")
_TOOL_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
# Từ (tách theo ký tự không phải chữ số) cho phép model đưa vào một mệnh đề hay câu truy vấn.
_FORBIDDEN_TOKENS = frozenset(
    {
        "sql",
        "query",
        "statement",
        "stmt",
        "where",
        "expression",
        "expr",
        "clause",
        "predicate",
        "condition",
        "raw",
        "cmd",
        "command",
    }
)
# Chuỗi con (sau khi bỏ dấu và dấu gạch) không được xuất hiện trong tên tham số, kể cả tiếng Việt.
_FORBIDDEN_SUBSTRINGS = ("sql", "truyvan", "caulenh", "dieukien", "bieuthuc", "orderby", "groupby")
# Chuỗi tự do (không phải enum) dài hơn mức này đủ chứa một câu SQL: không chấp nhận.
MAX_FREE_TEXT_LENGTH = 200


class ToolDefinitionError(ValueError):
    """Định nghĩa công cụ vi phạm quy tắc an toàn hay thiếu thông tin."""


class ToolArgumentError(ValueError):
    """Lời gọi công cụ có đối số không hợp lệ (model đưa vào): khóa lạ, sai kiểu, sai enum..."""


@dataclass(frozen=True, slots=True)
class ToolParameter:
    kind: ToolParameterKind
    description: str = ""
    # Chuỗi chỉ nhận một trong các giá trị này, hoặc phải có `max_length`.
    enum: tuple[str, ...] | None = None
    max_length: int | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class ChatTool:
    name: str
    description: str
    parameters: Mapping[str, ToolParameter]
    handler: Callable[..., Awaitable[Any]]

    def __post_init__(self) -> None:
        # Bản sao bất biến: sửa dict gốc (hay thêm tham số) sau khi dựng không đổi được công cụ.
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


def _normalised_name(name: str) -> tuple[list[str], str]:
    """Tên tham số bỏ dấu, hạ chữ thường, chuẩn hóa chữ toàn-rộng; trả (các từ, chuỗi nối liền)."""
    decomposed = unicodedata.normalize("NFKD", name).replace("đ", "d").replace("Đ", "D")
    plain = "".join(char for char in decomposed if not unicodedata.combining(char)).lower()
    tokens = [token for token in re.split(r"[^a-z0-9]+", plain) if token]
    return tokens, "".join(tokens)


def _validate_parameter(tool_name: str, name: str, parameter: ToolParameter) -> None:
    tokens, joined = _normalised_name(name)
    if any(token in _FORBIDDEN_TOKENS for token in tokens) or any(
        part in joined for part in _FORBIDDEN_SUBSTRINGS
    ):
        raise ToolDefinitionError(
            f"Công cụ {tool_name!r}: tham số {name!r} trông như SQL hay truy vấn tự do."
        )
    if parameter.kind not in _KINDS:
        raise ToolDefinitionError(f"Công cụ {tool_name!r}: tham số {name!r} có kiểu không hỗ trợ.")
    if parameter.enum is not None and (
        not parameter.enum or any(not item.strip() for item in parameter.enum)
    ):
        raise ToolDefinitionError(
            f"Công cụ {tool_name!r}: enum của {name!r} rỗng hay có giá trị rỗng."
        )
    limit = parameter.max_length
    if limit is not None and (isinstance(limit, bool) or limit <= 0):
        raise ToolDefinitionError(f"Công cụ {tool_name!r}: max_length của {name!r} phải dương.")
    if parameter.kind == "string" and parameter.enum is None:
        if limit is None or limit > MAX_FREE_TEXT_LENGTH:
            raise ToolDefinitionError(
                f"Công cụ {tool_name!r}: tham số chuỗi {name!r} phải là enum hoặc có "
                f"max_length tối đa {MAX_FREE_TEXT_LENGTH}."
            )


def validate_tool(tool: ChatTool) -> None:
    """Ném `ToolDefinitionError` nếu công cụ có thể nhận SQL hay truy vấn tự do từ model."""
    if not _TOOL_NAME.fullmatch(tool.name):
        raise ToolDefinitionError(
            f"Tên công cụ {tool.name!r} phải là định danh ASCII (chữ, số, gạch dưới, tối đa 64)."
        )
    if not tool.description.strip():
        raise ToolDefinitionError(f"Công cụ {tool.name!r} phải có mô tả.")
    for name, parameter in tool.parameters.items():
        _validate_parameter(tool.name, name, parameter)


def _coerce(tool_name: str, name: str, parameter: ToolParameter, value: Any) -> Any:
    """Kiểm một đối số theo khai báo và đổi sang giá trị Python đúng kiểu."""

    def fail(reason: str) -> ToolArgumentError:
        return ToolArgumentError(f"Công cụ {tool_name!r}: đối số {name!r} {reason}.")

    kind = parameter.kind
    if kind == "boolean":
        if not isinstance(value, bool):
            raise fail("phải là true hoặc false")
        return value
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise fail("phải là số nguyên")
        return value
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise fail("phải là số")
        return value
    if not isinstance(value, str):
        raise fail("phải là chuỗi")
    if kind == "uuid":
        try:
            return uuid.UUID(value)
        except ValueError:
            raise fail("không phải UUID hợp lệ") from None
    if kind == "date":
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise fail("phải có dạng YYYY-MM-DD") from None
    if parameter.enum is not None:
        if value not in parameter.enum:
            raise fail("không thuộc các giá trị cho phép")
        return value
    if parameter.max_length is not None and len(value) > parameter.max_length:
        raise fail(f"dài quá {parameter.max_length} ký tự")
    return value


def validate_arguments(tool: ChatTool, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Kiểm đối số do model đưa vào theo khai báo; trả đối số đã đổi kiểu. Khóa lạ bị từ chối."""
    unknown = set(arguments) - set(tool.parameters)
    if unknown:
        raise ToolArgumentError(f"Công cụ {tool.name!r}: không có đối số {sorted(unknown)!r}.")
    checked: dict[str, Any] = {}
    for name, parameter in tool.parameters.items():
        if name not in arguments:
            if parameter.required:
                raise ToolArgumentError(f"Công cụ {tool.name!r}: thiếu đối số {name!r}.")
            continue
        checked[name] = _coerce(tool.name, name, parameter, arguments[name])
    return checked


class ToolRegistry:
    """Danh sách công cụ đã đăng ký; chỉ nhận công cụ qua kiểm định, tên không trùng (không phân
    biệt hoa thường), và chỉ gọi công cụ qua kiểm đối số."""

    def __init__(self) -> None:
        self._tools: list[ChatTool] = []

    @property
    def tools(self) -> tuple[ChatTool, ...]:
        return tuple(self._tools)

    def register(self, tool: ChatTool) -> None:
        validate_tool(tool)
        if any(existing.name.lower() == tool.name.lower() for existing in self._tools):
            raise ToolDefinitionError(f"Công cụ {tool.name!r} đã được đăng ký.")
        self._tools.append(tool)

    async def call(self, name: str, arguments: Mapping[str, Any]) -> Any:
        """Gọi một công cụ: kiểm đối số trước, handler chỉ nhận đối số đã kiểm."""
        tool = next((item for item in self._tools if item.name == name), None)
        if tool is None:
            raise ToolArgumentError(f"Không có công cụ {name!r}.")
        return await tool.handler(**validate_arguments(tool, arguments))


_DEFAULT_REGISTRY = ToolRegistry()


def default_registry() -> ToolRegistry:
    """Sổ đăng ký dùng chung của tiến trình. Rỗng ở 5.1: công cụ đầu tiên đến ở 5.2."""
    return _DEFAULT_REGISTRY
