from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, Quote, QuoteLine, QuoteVersion, Supplier
from app.services.material_type_admin import normalize_catalog_code, normalize_optional_text
from app.services.quote_service import QuoteService

QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS: tuple[str, ...] = (
    "supplier_name",
    "received_date",
    "material_code",
    "price_original",
    "currency",
    "unit",
    "delivery_month",
    "exchange_rate",
    "import_tax_rate_percent",
    "processing_cost_vnd_per_kg",
    "note",
)
QUOTE_BACKFILL_IMPORT_TEMPLATE_FILENAME = "quote_backfill_import_template.csv"
QUOTE_BACKFILL_IMPORT_SAMPLE_ROW: tuple[str, ...] = (
    "Tập đoàn Tân Long (Tan Long Group)",
    "15/06/2026",
    "CORN",
    "300.00",
    "USD",
    "MT",
    "07/2026",
    "26100.00",
    "0.00",
    "200.00",
    "Ghi chú tùy chọn",
)


def normalize_supplier_name_for_matching(value: str) -> str:
    """Collapses extra whitespace and folds case so historical files that
    record the supplier's display name (not its catalog code) still match,
    even with minor spacing/casing differences. Used both for grouping rows
    into quotes and for resolving the name against `Supplier.name`."""
    return re.sub(r"\s+", " ", value.strip()).casefold()


@dataclass(slots=True, frozen=True)
class _SupplierMatchCandidate:
    id: UUID
    normalized_name: str
    normalized_code: str


# (supplier_id, received_date, material_id, delivery_month, currency, unit,
# price_original, exchange_rate, import_tax_rate_percent, processing_cost_vnd_per_kg)
_LineDedupKey = tuple[
    UUID,
    date,
    UUID,
    date,
    str,
    str,
    Decimal,
    Decimal | None,
    Decimal | None,
    Decimal | None,
]


def _resolve_supplier_id(
    candidates: Sequence[_SupplierMatchCandidate],
    supplier_name: str,
) -> UUID:
    """Resolves a historical file's `supplier_name` (often an abbreviation
    like "ADM" or "CJ", not the full `Supplier.name`) against the catalog.
    Tries exact name/code match first, then falls back to substring
    containment against name or code. Raises with a specific message when
    the match isn't confident (no candidate, or more than one) instead of
    guessing — see docs/quotify/plan-import-bao-gia-cu.md Decision #10."""
    normalized_input = normalize_supplier_name_for_matching(supplier_name)

    exact_matches = {
        candidate.id
        for candidate in candidates
        if normalized_input in (candidate.normalized_name, candidate.normalized_code)
    }
    if len(exact_matches) == 1:
        return next(iter(exact_matches))
    if len(exact_matches) > 1:
        raise ValueError(
            f"Tên nhà cung cấp '{supplier_name}' khớp nhiều hơn một nhà cung cấp trong hệ "
            "thống, vui lòng kiểm tra lại dữ liệu.",
        )

    contains_matches = {
        candidate.id
        for candidate in candidates
        if normalized_input in candidate.normalized_name
        or normalized_input in candidate.normalized_code
    }
    if len(contains_matches) == 1:
        return next(iter(contains_matches))
    if len(contains_matches) > 1:
        raise ValueError(
            f"Tên nhà cung cấp '{supplier_name}' khớp gần đúng với nhiều hơn một nhà cung cấp "
            "trong hệ thống, vui lòng kiểm tra lại dữ liệu.",
        )

    raise ValueError(f"Nhà cung cấp '{supplier_name}' không tồn tại.")

# Commit theo lô thay vì mỗi nhóm, để giảm round-trip ở quy mô hàng chục
# nghìn dòng — xem docs/quotify/plan-import-bao-gia-cu.md#Cân Nhắc Hiệu Năng.
COMMIT_BATCH_SIZE = 200


class QuoteBackfillImportHeaderError(Exception):
    """Raised when the backfill-import CSV header doesn't match the template."""


@dataclass(slots=True)
class QuoteBackfillImportSummary:
    total_rows: int = 0
    processed_rows: int = 0
    failed_rows: int = 0
    created_quote_count: int = 0
    created_line_count: int = 0
    failed_group_count: int = 0
    errors: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class _ParsedRow:
    row_number: int
    supplier_name: str
    received_date: date
    material_code: str
    price_original: Decimal
    currency: str
    unit: str
    delivery_month: date
    exchange_rate: Decimal | None
    import_tax_rate_percent: Decimal | None
    processing_cost_vnd_per_kg: Decimal | None
    note: str | None


def validate_quote_backfill_import_headers(fieldnames: Sequence[str] | None) -> None:
    received_headers = tuple(fieldnames or ())
    if received_headers != QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS:
        expected = ", ".join(QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS)
        received = ", ".join(received_headers) if received_headers else "(không có header)"
        raise QuoteBackfillImportHeaderError(
            f"Header CSV không hợp lệ. Cần: {expected}. Nhận: {received}.",
        )


def build_quote_backfill_import_template() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS)
    writer.writerow(QUOTE_BACKFILL_IMPORT_SAMPLE_ROW)
    return buffer.getvalue().encode("utf-8-sig")


def build_quote_backfill_import_error_report(job_errors: list[Any] | None) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "errors"])
    for item in job_errors or []:
        if not isinstance(item, dict):
            continue
        errors = item.get("errors")
        if isinstance(errors, list):
            error_text = "; ".join(str(error) for error in errors)
        else:
            error_text = str(errors or "")
        writer.writerow([item.get("row", ""), error_text])
    return buffer.getvalue().encode("utf-8-sig")


def _require_field(row: dict[str, str | None], key: str, label: str) -> str:
    value = normalize_optional_text(row.get(key))
    if value is None:
        raise ValueError(f"{label} là bắt buộc.")
    return value


def _parse_decimal(value: str, label: str, *, require_integer: bool = False) -> Decimal:
    # File thực tế xuất từ Excel hay định dạng số lớn kèm dấu phẩy ngăn hàng
    # nghìn (ví dụ "26,466"), trong khi dấu chấm luôn dùng cho phần thập phân
    # trong toàn bộ file — bỏ dấu phẩy ngăn hàng nghìn trước khi parse.
    try:
        parsed = Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"{label} không phải là số hợp lệ.") from exc

    # Tỷ giá VNĐ/USD luôn là số nguyên trên thực tế (không có phần lẻ đồng),
    # khác với giá gốc USD/MT vốn có thể có phần thập phân (cent).
    if require_integer and parsed != parsed.to_integral_value():
        raise ValueError(f"{label} phải là số nguyên.")

    return parsed


def _parse_optional_decimal(
    row: dict[str, str | None],
    key: str,
    label: str,
    *,
    require_integer: bool = False,
) -> Decimal | None:
    raw = normalize_optional_text(row.get(key))
    if raw is None:
        return None
    return _parse_decimal(raw, label, require_integer=require_integer)


def parse_quote_backfill_import_row(row_number: int, row: dict[str, str | None]) -> _ParsedRow:
    """Parses and validates a single CSV row. Raises `ValueError` with a
    Vietnamese message describing the first problem found; does not touch the
    database (no supplier/material code resolution here — that is batched
    separately for performance, see `QuoteBackfillImportService`)."""
    supplier_name = re.sub(r"\s+", " ", _require_field(row, "supplier_name", "Tên nhà cung cấp"))
    material_code = normalize_catalog_code(_require_field(row, "material_code", "Mã vật tư"))

    received_date_raw = _require_field(row, "received_date", "Ngày nhận báo giá")
    try:
        received_date = datetime.strptime(received_date_raw, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValueError("Ngày nhận báo giá phải theo định dạng DD/MM/YYYY.") from exc

    delivery_month_raw = _require_field(row, "delivery_month", "Kỳ giao hàng")
    try:
        delivery_month = datetime.strptime(delivery_month_raw, "%m/%Y").date()
    except ValueError as exc:
        raise ValueError("Kỳ giao hàng phải theo định dạng MM/YYYY.") from exc

    price_original = _parse_decimal(_require_field(row, "price_original", "Giá gốc"), "Giá gốc")
    currency = _require_field(row, "currency", "Tiền tệ").upper()
    unit = _require_field(row, "unit", "Đơn vị").upper()

    exchange_rate = _parse_optional_decimal(
        row, "exchange_rate", "Tỷ giá", require_integer=True,
    )
    import_tax_rate_percent = _parse_optional_decimal(
        row, "import_tax_rate_percent", "Thuế nhập khẩu",
    )
    processing_cost_vnd_per_kg = _parse_optional_decimal(
        row, "processing_cost_vnd_per_kg", "Chi phí làm hàng",
    )
    note = normalize_optional_text(row.get("note"))

    historical_values = (exchange_rate, import_tax_rate_percent, processing_cost_vnd_per_kg)
    if currency == "VND" and unit == "KG":
        if any(value is not None for value in historical_values):
            raise ValueError(
                "Dòng VND/KG không được nhập tỷ giá, thuế nhập khẩu hoặc chi phí làm hàng.",
            )
    elif currency == "USD" and unit == "MT":
        if any(value is None for value in historical_values):
            raise ValueError(
                "Dòng USD/MT bắt buộc phải nhập đủ tỷ giá, thuế nhập khẩu và chi phí làm hàng "
                "tại thời điểm báo giá.",
            )
    else:
        raise ValueError(
            f"Cặp tiền tệ/đơn vị '{currency}/{unit}' không hợp lệ. Chỉ hỗ trợ VND/KG hoặc USD/MT.",
        )

    return _ParsedRow(
        row_number=row_number,
        supplier_name=supplier_name,
        received_date=received_date,
        material_code=material_code,
        price_original=price_original,
        currency=currency,
        unit=unit,
        delivery_month=delivery_month,
        exchange_rate=exchange_rate,
        import_tax_rate_percent=import_tax_rate_percent,
        processing_cost_vnd_per_kg=processing_cost_vnd_per_kg,
        note=note,
    )


class QuoteBackfillImportService:
    def __init__(self, session: AsyncSession, quote_service: QuoteService) -> None:
        self.session = session
        self.quote_service = quote_service

    async def import_rows(
        self,
        *,
        rows: Iterable[dict[str, str | None]],
        fieldnames: Sequence[str] | None,
        created_by_id: UUID,
    ) -> QuoteBackfillImportSummary:
        validate_quote_backfill_import_headers(fieldnames)

        summary = QuoteBackfillImportSummary()
        groups: dict[tuple[str, date], list[_ParsedRow]] = {}
        group_order: list[tuple[str, date]] = []

        for row_number, raw_row in enumerate(rows, start=1):
            summary.total_rows = row_number
            try:
                parsed = parse_quote_backfill_import_row(row_number, raw_row)
            except ValueError as exc:
                summary.failed_rows += 1
                summary.failed_group_count += 1
                summary.errors.append({"row": row_number, "errors": [str(exc)]})
                continue

            key = (normalize_supplier_name_for_matching(parsed.supplier_name), parsed.received_date)
            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(parsed)

        if not group_order:
            return summary

        # Nạp trước toàn bộ mapping NCC/vật tư -> id trong 2 truy vấn duy nhất,
        # thay vì query theo từng dòng — xem "Cân Nhắc Hiệu Năng" trong kế
        # hoạch. Nạp toàn bộ NCC (không lọc theo IN(...)) vì so khớp theo tên
        # đã chuẩn hóa (bỏ khoảng trắng dư, không phân biệt hoa/thường) không
        # thể lọc chính xác bằng SQL; số lượng NCC trong hệ thống nhỏ nên tải
        # hết vẫn rẻ hơn nhiều so với query theo từng dòng.
        supplier_candidates = await self._load_supplier_candidates()
        material_ids_by_code = await self._load_material_ids(
            {row.material_code for rows_in_group in groups.values() for row in rows_in_group},
        )

        # Phân giải NCC trước cho toàn bộ nhóm (không tốn DB, chỉ so khớp
        # trong bộ nhớ) để biết trước tập (supplier_id, received_date) cần
        # kiểm tra trùng lặp, rồi tải 1 lần duy nhất — tránh query theo từng
        # nhóm ở quy mô hàng chục nghìn dòng.
        resolved_supplier_id_by_key: dict[tuple[str, date], UUID] = {}
        for key in group_order:
            group_rows = groups[key]
            try:
                resolved_supplier_id_by_key[key] = _resolve_supplier_id(
                    supplier_candidates,
                    group_rows[0].supplier_name,
                )
            except ValueError as exc:
                summary.failed_rows += len(group_rows)
                summary.failed_group_count += 1
                row_numbers = ", ".join(str(row.row_number) for row in group_rows)
                summary.errors.append(
                    {
                        "row": group_rows[0].row_number,
                        "errors": [f"Nhóm dòng {row_numbers}: {exc}"],
                    },
                )

        existing_line_keys = await self._load_existing_line_keys(
            supplier_ids={supplier_id for supplier_id in resolved_supplier_id_by_key.values()},
            received_dates={key[1] for key in resolved_supplier_id_by_key},
        )

        groups_since_commit = 0
        for key in group_order:
            supplier_id = resolved_supplier_id_by_key.get(key)
            if supplier_id is None:
                continue

            group_rows = groups[key]
            try:
                async with self.session.begin_nested():
                    line_count = await self._create_quote_from_group(
                        group_rows,
                        created_by_id=created_by_id,
                        supplier_id=supplier_id,
                        material_ids_by_code=material_ids_by_code,
                        existing_line_keys=existing_line_keys,
                    )
            except Exception as exc:  # noqa: BLE001
                summary.failed_rows += len(group_rows)
                summary.failed_group_count += 1
                row_numbers = ", ".join(str(row.row_number) for row in group_rows)
                summary.errors.append(
                    {
                        "row": group_rows[0].row_number,
                        "errors": [f"Nhóm dòng {row_numbers}: {exc}"],
                    },
                )
            else:
                summary.processed_rows += len(group_rows)
                summary.created_quote_count += 1
                summary.created_line_count += line_count

            groups_since_commit += 1
            if groups_since_commit >= COMMIT_BATCH_SIZE:
                await self.session.commit()
                groups_since_commit = 0

        if groups_since_commit > 0:
            await self.session.commit()

        return summary

    async def _load_supplier_candidates(self) -> list[_SupplierMatchCandidate]:
        result = await self.session.execute(select(Supplier.name, Supplier.code, Supplier.id))
        return [
            _SupplierMatchCandidate(
                id=supplier_id,
                normalized_name=normalize_supplier_name_for_matching(name),
                normalized_code=normalize_supplier_name_for_matching(code),
            )
            for name, code, supplier_id in result.all()
        ]

    async def _load_material_ids(self, codes: set[str]) -> dict[str, UUID]:
        if not codes:
            return {}
        result = await self.session.execute(
            select(Material.code, Material.id).where(Material.code.in_(codes)),
        )
        return {code: material_id for code, material_id in result.all()}

    async def _load_existing_line_keys(
        self,
        *,
        supplier_ids: set[UUID],
        received_dates: set[date],
    ) -> set[_LineDedupKey]:
        """Loads a lookup of every existing line's full business data (NCC +
        ngày + vật tư + giá + kỳ giao...) restricted to the suppliers/dates
        touched by this import, so duplicate detection is O(1) per row
        instead of one query per row — see docs/quotify/plan-import-bao-gia-cu.md
        (quyết định "trùng hoàn toàn dữ liệu" ngày 12/08/2026)."""
        if not supplier_ids or not received_dates:
            return set()

        result = await self.session.execute(
            select(
                Quote.supplier_id,
                QuoteVersion.received_date,
                QuoteLine.material_id,
                QuoteLine.delivery_month,
                QuoteLine.currency,
                QuoteLine.unit,
                QuoteLine.price_original,
                QuoteLine.exchange_rate,
                QuoteLine.import_tax_rate_percent,
                QuoteLine.processing_cost_vnd_per_kg,
            )
            .join(QuoteVersion, QuoteVersion.id == QuoteLine.quote_version_id)
            .join(Quote, Quote.id == QuoteVersion.quote_id)
            .where(
                Quote.supplier_id.in_(supplier_ids),
                QuoteVersion.received_date.in_(received_dates),
            ),
        )
        return {tuple(row) for row in result.all()}  # type: ignore[misc]

    async def _create_quote_from_group(
        self,
        group_rows: list[_ParsedRow],
        *,
        created_by_id: UUID,
        supplier_id: UUID,
        material_ids_by_code: dict[str, UUID],
        existing_line_keys: set[_LineDedupKey],
    ) -> int:
        received_date = group_rows[0].received_date

        lines_data: list[dict[str, object]] = []
        for row in group_rows:
            material_id = material_ids_by_code.get(row.material_code)
            if material_id is None:
                raise ValueError(f"Vật tư '{row.material_code}' không tồn tại.")

            dedup_key = (
                supplier_id,
                received_date,
                material_id,
                row.delivery_month,
                row.currency,
                row.unit,
                row.price_original,
                row.exchange_rate,
                row.import_tax_rate_percent,
                row.processing_cost_vnd_per_kg,
            )
            if dedup_key in existing_line_keys:
                raise ValueError(
                    f"Dòng {row.row_number}: báo giá này đã tồn tại trong hệ thống "
                    "(trùng lặp hoàn toàn dữ liệu NCC/ngày/vật tư/giá/kỳ giao hàng).",
                )

            lines_data.append(
                {
                    "material_id": material_id,
                    "price_original": row.price_original,
                    "currency": row.currency,
                    "unit": row.unit,
                    "delivery_month": row.delivery_month,
                    "exchange_rate": row.exchange_rate,
                    "import_tax_rate_percent": row.import_tax_rate_percent,
                    "processing_cost_vnd_per_kg": row.processing_cost_vnd_per_kg,
                    "note": row.note,
                },
            )

        await self.quote_service.create_quote(
            supplier_id=supplier_id,
            received_date=received_date,
            is_backfilled=True,
            backfill_reason=None,
            lines_data=lines_data,
            created_by_id=created_by_id,
            confirm_immediately=True,
            skip_reload=True,
        )
        return len(lines_data)
