"""Sổ đăng ký công cụ của chatbot: không công cụ nào nhận SQL hay truy vấn tự do từ model (5.1, S6).

Engine DB chỉ đọc chỉ là rào chắn (RC-27); an toàn thật dựa vào việc model không bao giờ đưa được
SQL vào hệ thống. Công cụ của 5.2 phải đăng ký qua đây và bị từ chối nếu nhận tham số kiểu đó.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.services.chat_tools import (
    MAX_FREE_TEXT_LENGTH,
    ChatTool,
    ToolArgumentError,
    ToolDefinitionError,
    ToolParameter,
    ToolRegistry,
    default_registry,
    validate_arguments,
    validate_tool,
)


async def _handler(**arguments: object) -> str:
    return "ok"


def _tool(**parameters: ToolParameter) -> ChatTool:
    return ChatTool(
        name="tra_cuu_gia",
        description="Tra giá gần nhất của một mặt hàng",
        parameters=parameters,
        handler=_handler,
    )


def test_the_pipeline_itself_registers_no_tools() -> None:
    # 5.1 chỉ dựng đường ống; công cụ đầu tiên đến ở 5.2 và phải qua kiểm định bên dưới.
    assert default_registry().tools == ()


def test_every_tool_in_the_default_registry_passes_the_validation() -> None:
    for tool in default_registry().tools:
        validate_tool(tool)  # rỗng ở 5.1; bảo vệ công cụ của 5.2 tự động


@pytest.mark.parametrize(
    "name",
    [
        "sql",
        "query_sql",
        "SQL",
        "raw_sql",
        "sql_where",
        "statement",
        "where",
        "query",
        "expression",
    ],
)
def test_a_parameter_that_looks_like_sql_or_a_free_query_is_rejected(name: str) -> None:
    tool = _tool(**{name: ToolParameter("string", max_length=50)})

    with pytest.raises(ToolDefinitionError):
        validate_tool(tool)


def test_a_free_text_parameter_must_be_bounded_or_an_enum() -> None:
    with pytest.raises(ToolDefinitionError):
        validate_tool(_tool(tu_khoa=ToolParameter("string")))  # không giới hạn độ dài
    with pytest.raises(ToolDefinitionError):
        validate_tool(
            _tool(tu_khoa=ToolParameter("string", max_length=5000))
        )  # dài như một câu SQL

    validate_tool(_tool(tu_khoa=ToolParameter("string", max_length=100)))
    validate_tool(_tool(trang_thai=ToolParameter("string", enum=("moi", "da_duyet"))))


def test_the_free_text_length_limit_is_inclusive_at_the_boundary() -> None:
    validate_tool(_tool(tu_khoa=ToolParameter("string", max_length=MAX_FREE_TEXT_LENGTH)))
    with pytest.raises(ToolDefinitionError):
        validate_tool(_tool(tu_khoa=ToolParameter("string", max_length=MAX_FREE_TEXT_LENGTH + 1)))


def test_typed_parameters_are_accepted() -> None:
    validate_tool(
        _tool(
            ma_hang=ToolParameter("uuid"),
            so_luong=ToolParameter("integer"),
            don_gia=ToolParameter("number"),
            co_vat=ToolParameter("boolean"),
            ngay=ToolParameter("date", required=False),
        )
    )


def test_a_tool_needs_a_name_a_description_and_a_known_parameter_kind() -> None:
    with pytest.raises(ToolDefinitionError):
        validate_tool(ChatTool(name="", description="x", parameters={}, handler=_handler))
    with pytest.raises(ToolDefinitionError):
        validate_tool(ChatTool(name="ten", description="  ", parameters={}, handler=_handler))
    with pytest.raises(ToolDefinitionError):
        validate_tool(_tool(x=ToolParameter("object")))  # type: ignore[arg-type]


def test_the_registry_validates_on_register_and_refuses_duplicate_names() -> None:
    registry = ToolRegistry()
    good = _tool(so_luong=ToolParameter("integer"))

    registry.register(good)

    assert registry.tools == (good,)
    with pytest.raises(ToolDefinitionError):
        registry.register(good)  # trùng tên
    with pytest.raises(ToolDefinitionError):
        registry.register(
            ChatTool(
                name="tool_khac",
                description="x",
                parameters={"sql": ToolParameter("string", max_length=10)},
                handler=_handler,
            )
        )
    assert registry.tools == (good,)  # công cụ bị từ chối không lọt vào sổ


@pytest.mark.parametrize(
    "name",
    [
        "where_clause",
        "search_query",
        "ma_truy_van",
        "truy_vấn",  # có dấu
        "cau_lenh",
        "dieu_kien",
        "bieu_thuc",
        "order_by",
        "group_by",
        "raw",
        "expr",
        "stmt",
        "condition",
        "predicate",
        "cmd",
        "command",
        "ｑｕｅｒｙ",  # chữ toàn-rộng
        "điều_kiện",  # có dấu và chữ đ
        "biểu_thức",
        "câu_lệnh",
        "quéry",  # dấu nằm giữa từ bị cấm
        "whêre",
        "s_q_l",
        "Sql",
        "NoSQL",
    ],
)
def test_names_that_hide_sql_or_a_query_are_rejected_after_normalising(name: str) -> None:
    with pytest.raises(ToolDefinitionError):
        validate_tool(_tool(**{name: ToolParameter("string", max_length=50)}))


@pytest.mark.parametrize("name", ["ma_hang", "so_luong", "tu_khoa", "ngay_bao_gia", "trang_thai"])
def test_ordinary_vietnamese_parameter_names_are_accepted(name: str) -> None:
    validate_tool(_tool(**{name: ToolParameter("integer")}))


@pytest.mark.parametrize("name", ["", "Tra Cuu", "tra-cuu", "1tra_cuu", "tra_cuu_giá", "a" * 65])
def test_a_tool_name_must_be_a_plain_identifier(name: str) -> None:
    with pytest.raises(ToolDefinitionError):
        validate_tool(ChatTool(name=name, description="x", parameters={}, handler=_handler))


def test_tool_names_that_differ_only_by_case_count_as_duplicates() -> None:
    registry = ToolRegistry()
    registry.register(ChatTool(name="tra_cuu", description="x", parameters={}, handler=_handler))

    with pytest.raises(ToolDefinitionError):
        registry.register(
            ChatTool(name="Tra_Cuu", description="x", parameters={}, handler=_handler)
        )


@pytest.mark.parametrize(
    "parameter",
    [
        ToolParameter("string", enum=()),  # enum rỗng
        ToolParameter("string", enum=("", "ok")),  # giá trị rỗng
        ToolParameter("string", max_length=0),
        ToolParameter("string", max_length=-5),
        ToolParameter("string", max_length=True),  # bool không phải độ dài
    ],
)
def test_a_degenerate_enum_or_length_is_rejected(parameter: ToolParameter) -> None:
    with pytest.raises(ToolDefinitionError):
        validate_tool(_tool(tu_khoa=parameter))


def test_the_parameters_of_a_tool_cannot_be_changed_after_it_was_built() -> None:
    parameters = {"so_luong": ToolParameter("integer")}
    tool = _tool(**parameters)

    parameters["sql"] = ToolParameter("string", max_length=10)  # sửa dict gốc

    assert set(tool.parameters) == {"so_luong"}  # công cụ đã dựng không bị đổi
    with pytest.raises(TypeError):
        tool.parameters["sql"] = ToolParameter("string", max_length=10)  # type: ignore[index]


# --- kiểm lúc gọi: khóa lạ, sai kiểu, sai enum, quá dài bị từ chối trước khi handler thấy ----


def _typed_tool() -> ChatTool:
    return _tool(
        ma_hang=ToolParameter("uuid"),
        so_luong=ToolParameter("integer"),
        don_gia=ToolParameter("number", required=False),
        co_vat=ToolParameter("boolean", required=False),
        ngay=ToolParameter("date", required=False),
        tu_khoa=ToolParameter("string", max_length=10, required=False),
        trang_thai=ToolParameter("string", enum=("moi", "da_duyet"), required=False),
    )


def test_valid_arguments_come_back_as_typed_values() -> None:
    item = uuid.uuid4()

    arguments = validate_arguments(
        _typed_tool(),
        {
            "ma_hang": str(item),
            "so_luong": 3,
            "don_gia": 12.5,
            "co_vat": True,
            "ngay": "2026-10-14",
            "tu_khoa": "thép",
            "trang_thai": "moi",
        },
    )

    assert arguments == {
        "ma_hang": item,
        "so_luong": 3,
        "don_gia": 12.5,
        "co_vat": True,
        "ngay": date(2026, 10, 14),
        "tu_khoa": "thép",
        "trang_thai": "moi",
    }


def test_an_integer_is_a_valid_number_and_optional_arguments_may_be_missing() -> None:
    arguments = validate_arguments(
        _typed_tool(), {"ma_hang": str(uuid.uuid4()), "so_luong": 1, "don_gia": 7}
    )

    assert arguments["don_gia"] == 7 and set(arguments) == {"ma_hang", "so_luong", "don_gia"}


@pytest.mark.parametrize(
    "arguments",
    [
        {"so_luong": 1},  # thiếu ma_hang (bắt buộc)
        {"ma_hang": "không-phải-uuid", "so_luong": 1},
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": "5"},  # chuỗi cho số nguyên
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": True},  # bool không phải số
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": 1.5},
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": 1, "don_gia": True},
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": 1, "co_vat": 1},
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": 1, "ngay": "14/10/2026"},
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": 1, "tu_khoa": "x" * 11},
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": 1, "tu_khoa": 5},
        {"ma_hang": "00000000-0000-0000-0000-000000000000", "so_luong": 1, "trang_thai": "khac"},
        {
            "ma_hang": "00000000-0000-0000-0000-000000000000",
            "so_luong": 1,
            "sql": "drop table users",
        },
    ],
)
def test_invalid_arguments_are_rejected(arguments: dict[str, object]) -> None:
    with pytest.raises(ToolArgumentError):
        validate_arguments(_typed_tool(), arguments)


async def test_calling_through_the_registry_validates_first_and_passes_only_typed_values() -> None:
    received: list[dict[str, object]] = []

    async def handler(**arguments: object) -> str:
        received.append(arguments)
        return "xong"

    registry = ToolRegistry()
    registry.register(
        ChatTool(
            name="dem_hang",
            description="Đếm hàng",
            parameters={"so_luong": ToolParameter("integer")},
            handler=handler,
        )
    )

    assert await registry.call("dem_hang", {"so_luong": 4}) == "xong"
    assert received == [{"so_luong": 4}]
    with pytest.raises(ToolArgumentError):
        await registry.call("dem_hang", {"so_luong": 4, "sql": "drop table users"})
    with pytest.raises(ToolArgumentError):
        await registry.call("khong_co", {})
    assert received == [{"so_luong": 4}]  # handler không bao giờ thấy lời gọi bị từ chối
