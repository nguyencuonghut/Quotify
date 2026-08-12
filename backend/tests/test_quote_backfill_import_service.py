from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.quote_backfill_import import (
    QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
    QuoteBackfillImportHeaderError,
    QuoteBackfillImportService,
    _resolve_supplier_id,
    _SupplierMatchCandidate,
    build_quote_backfill_import_error_report,
    build_quote_backfill_import_template,
    normalize_supplier_name_for_matching,
    parse_quote_backfill_import_row,
    validate_quote_backfill_import_headers,
)


def _usd_row(**overrides: str | None) -> dict[str, str | None]:
    row: dict[str, str | None] = {
        "supplier_name": "  Tập đoàn Tân Long (Tan Long Group)  ",
        "received_date": "15/06/2026",
        "material_code": "corn",
        "price_original": "300.00",
        "currency": "USD",
        "unit": "MT",
        "delivery_month": "07/2026",
        "exchange_rate": "26100.00",
        "import_tax_rate_percent": "5.00",
        "processing_cost_vnd_per_kg": "200.00",
        "note": "  Ghi chú  ",
    }
    row.update(overrides)
    return row


def _vnd_row(**overrides: str | None) -> dict[str, str | None]:
    row: dict[str, str | None] = {
        "supplier_name": "Tập đoàn Tân Long (Tan Long Group)",
        "received_date": "15/06/2026",
        "material_code": "corn",
        "price_original": "15000.00",
        "currency": "VND",
        "unit": "KG",
        "delivery_month": "07/2026",
        "exchange_rate": None,
        "import_tax_rate_percent": None,
        "processing_cost_vnd_per_kg": None,
        "note": None,
    }
    row.update(overrides)
    return row


class TestNormalizeSupplierNameForMatching:
    def test_collapses_whitespace_and_folds_case(self) -> None:
        assert normalize_supplier_name_for_matching("  Tân   Long  ") == "tân long"
        normalized_upper = normalize_supplier_name_for_matching("TÂN LONG")
        normalized_lower = normalize_supplier_name_for_matching("tân long")
        assert normalized_upper == normalized_lower


def _candidate(name: str, code: str) -> _SupplierMatchCandidate:
    return _SupplierMatchCandidate(
        id=uuid4(),
        normalized_name=normalize_supplier_name_for_matching(name),
        normalized_code=normalize_supplier_name_for_matching(code),
    )


class TestResolveSupplierId:
    """Real historical files often record a short/abbreviated supplier name
    (e.g. "ADM", "CJ") instead of the full `Supplier.name` — see
    docs/quotify/plan-import-bao-gia-cu.md Decision #10."""

    def test_matches_exact_code_when_input_is_the_code(self) -> None:
        adm = _candidate("Archer Daniels Midland (ADM Asia)", "ADM")

        assert _resolve_supplier_id([adm], "ADM") == adm.id

    def test_matches_by_substring_of_name(self) -> None:
        tan_long = _candidate(TAN_LONG_NAME, "TAN_LONG")

        assert _resolve_supplier_id([tan_long], "Tân Long") == tan_long.id

    def test_matches_by_substring_of_code(self) -> None:
        cj = _candidate("CJ Vina Agri (CJ CheilJedang)", "CJ_VINA")

        assert _resolve_supplier_id([cj], "CJ") == cj.id

    def test_prefers_exact_match_over_ambiguous_substring(self) -> None:
        exact = _candidate("ADM", "ADM_ALT")
        substring_only = _candidate("Archer Daniels Midland (ADM Asia)", "ADM_ASIA")

        assert _resolve_supplier_id([exact, substring_only], "ADM") == exact.id

    def test_raises_when_no_candidate_matches(self) -> None:
        tan_long = _candidate(TAN_LONG_NAME, "TAN_LONG")

        with pytest.raises(ValueError, match="không tồn tại"):
            _resolve_supplier_id([tan_long], "Unknown Corp")

    def test_raises_when_substring_match_is_ambiguous(self) -> None:
        cargill = _candidate("Cargill Việt Nam (Cargill Vietnam)", "CARGILL_VN")
        cargill_asia = _candidate("Cargill Asia Holdings", "CARGILL_ASIA")

        with pytest.raises(ValueError, match="khớp gần đúng"):
            _resolve_supplier_id([cargill, cargill_asia], "Cargill")


class TestParseQuoteBackfillImportRow:
    def test_parses_valid_usd_mt_row(self) -> None:
        parsed = parse_quote_backfill_import_row(1, _usd_row())

        assert parsed.supplier_name == "Tập đoàn Tân Long (Tan Long Group)"
        assert parsed.material_code == "CORN"
        assert parsed.received_date == date(2026, 6, 15)
        assert parsed.delivery_month == date(2026, 7, 1)
        assert parsed.price_original == Decimal("300.00")
        assert parsed.exchange_rate == Decimal("26100.00")
        assert parsed.import_tax_rate_percent == Decimal("5.00")
        assert parsed.processing_cost_vnd_per_kg == Decimal("200.00")
        assert parsed.note == "Ghi chú"

    def test_parses_numeric_fields_with_thousands_separator_comma(self) -> None:
        """File thực tế xuất từ Excel định dạng số lớn kèm dấu phẩy ngăn hàng
        nghìn (ví dụ tỷ giá "26,466") — không phải dấu thập phân."""
        parsed = parse_quote_backfill_import_row(
            1,
            _usd_row(exchange_rate="26,466", price_original="1,259.00"),
        )

        assert parsed.exchange_rate == Decimal("26466")
        assert parsed.price_original == Decimal("1259.00")

    def test_allows_decimal_price_original(self) -> None:
        """Giá gốc USD/MT có thể có phần thập phân (cent)."""
        parsed = parse_quote_backfill_import_row(1, _usd_row(price_original="259.75"))

        assert parsed.price_original == Decimal("259.75")

    def test_rejects_non_integer_exchange_rate(self) -> None:
        """Tỷ giá VNĐ/USD luôn là số nguyên trên thực tế, khác với giá gốc."""
        row = _usd_row(exchange_rate="26466.50")
        with pytest.raises(ValueError, match="Tỷ giá phải là số nguyên"):
            parse_quote_backfill_import_row(1, row)

    def test_accepts_whole_number_exchange_rate_with_zero_decimal(self) -> None:
        parsed = parse_quote_backfill_import_row(1, _usd_row(exchange_rate="26466.00"))

        assert parsed.exchange_rate == Decimal("26466.00")

    def test_collapses_internal_double_spaces_in_supplier_name(self) -> None:
        parsed = parse_quote_backfill_import_row(
            1,
            _usd_row(supplier_name="Tập  đoàn   Tân Long"),
        )

        assert parsed.supplier_name == "Tập đoàn Tân Long"

    def test_parses_valid_vnd_kg_row_without_historical_values(self) -> None:
        parsed = parse_quote_backfill_import_row(1, _vnd_row())

        assert parsed.currency == "VND"
        assert parsed.unit == "KG"
        assert parsed.exchange_rate is None
        assert parsed.import_tax_rate_percent is None
        assert parsed.processing_cost_vnd_per_kg is None
        assert parsed.note is None

    @pytest.mark.parametrize(
        "missing_field",
        ["exchange_rate", "import_tax_rate_percent", "processing_cost_vnd_per_kg"],
    )
    def test_usd_mt_row_requires_all_three_historical_values(
        self,
        missing_field: str,
    ) -> None:
        row = _usd_row(**{missing_field: None})
        with pytest.raises(ValueError, match="bắt buộc phải nhập đủ"):
            parse_quote_backfill_import_row(1, row)

    @pytest.mark.parametrize(
        "extra_field",
        ["exchange_rate", "import_tax_rate_percent", "processing_cost_vnd_per_kg"],
    )
    def test_vnd_kg_row_rejects_historical_values(self, extra_field: str) -> None:
        row = _vnd_row(**{extra_field: "1.00"})
        with pytest.raises(ValueError, match="không được nhập"):
            parse_quote_backfill_import_row(1, row)

    def test_rejects_unsupported_currency_unit_pair(self) -> None:
        row = _usd_row(currency="USD", unit="KG")
        with pytest.raises(ValueError, match="không hợp lệ"):
            parse_quote_backfill_import_row(1, row)

    def test_rejects_invalid_received_date_format(self) -> None:
        row = _vnd_row(received_date="2026-06-15")
        with pytest.raises(ValueError, match="DD/MM/YYYY"):
            parse_quote_backfill_import_row(1, row)

    def test_rejects_invalid_delivery_month_format(self) -> None:
        row = _vnd_row(delivery_month="2026-07")
        with pytest.raises(ValueError, match="MM/YYYY"):
            parse_quote_backfill_import_row(1, row)

    def test_rejects_missing_required_field(self) -> None:
        row = _vnd_row(supplier_name=None)
        with pytest.raises(ValueError, match="Tên nhà cung cấp là bắt buộc"):
            parse_quote_backfill_import_row(1, row)

    def test_rejects_unparseable_decimal(self) -> None:
        row = _vnd_row(price_original="not-a-number")
        with pytest.raises(ValueError, match="không phải là số hợp lệ"):
            parse_quote_backfill_import_row(1, row)


class TestHeaderAndReportBuilders:
    def test_validate_headers_accepts_exact_match(self) -> None:
        validate_quote_backfill_import_headers(QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS)

    def test_validate_headers_rejects_mismatch(self) -> None:
        with pytest.raises(QuoteBackfillImportHeaderError):
            validate_quote_backfill_import_headers(("supplier_name", "received_date"))

    def test_template_contains_expected_headers_and_sample_row(self) -> None:
        content = build_quote_backfill_import_template().decode("utf-8-sig")
        first_line = content.splitlines()[0]
        assert first_line == ",".join(QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS)

    def test_error_report_formats_row_and_joined_errors(self) -> None:
        content = build_quote_backfill_import_error_report(
            [{"row": 3, "errors": ["Lỗi A", "Lỗi B"]}],
        ).decode("utf-8-sig")
        lines = content.splitlines()
        assert lines[0] == "row,errors"
        assert lines[1] == "3,Lỗi A; Lỗi B"


class FakeNestedTransaction:
    async def __aenter__(self) -> FakeNestedTransaction:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            raise exc_val


class FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Any, ...]]:
        return self._rows


class FakeSession:
    def __init__(
        self,
        *,
        suppliers: list[tuple[str, str, UUID]],
        material_ids_by_code: dict[str, UUID],
        existing_lines: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self.suppliers = suppliers
        self.material_ids_by_code = material_ids_by_code
        self.existing_lines = existing_lines or []
        self.commit_count = 0

    async def execute(self, statement: object) -> FakeResult:
        compiled = str(statement)
        if "FROM suppliers" in compiled:
            return FakeResult(self.suppliers)
        if "FROM materials" in compiled:
            return FakeResult(list(self.material_ids_by_code.items()))
        if "FROM quote_lines" in compiled:
            return FakeResult(self.existing_lines)
        raise AssertionError(f"Unexpected statement: {compiled}")

    def begin_nested(self) -> FakeNestedTransaction:
        return FakeNestedTransaction()

    async def commit(self) -> None:
        self.commit_count += 1


@dataclass
class _RecordedCall:
    supplier_id: UUID
    received_date: date
    lines_data: list[dict[str, object]]


class FakeQuoteService:
    def __init__(self, *, fail_for_supplier_ids: set[UUID] | None = None) -> None:
        self.calls: list[_RecordedCall] = []
        self.fail_for_supplier_ids = fail_for_supplier_ids or set()

    async def create_quote(
        self,
        *,
        supplier_id: UUID,
        received_date: date,
        is_backfilled: bool,
        backfill_reason: str | None,
        lines_data: list[dict[str, object]],
        created_by_id: UUID,
        confirm_immediately: bool = False,
        skip_reload: bool = False,
    ) -> object:
        assert is_backfilled is True
        assert confirm_immediately is True
        assert skip_reload is True
        if supplier_id in self.fail_for_supplier_ids:
            raise ValueError("Nhà cung cấp không tồn tại.")
        self.calls.append(
            _RecordedCall(
                supplier_id=supplier_id,
                received_date=received_date,
                lines_data=lines_data,
            ),
        )
        return object()


TAN_LONG_NAME = "Tập đoàn Tân Long (Tan Long Group)"


@pytest.mark.asyncio
async def test_import_rows_groups_by_supplier_and_received_date() -> None:
    supplier_id = uuid4()
    material_id = uuid4()
    session = FakeSession(
        suppliers=[(TAN_LONG_NAME, "TAN_LONG", supplier_id)],
        material_ids_by_code={"CORN": material_id},
    )
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    rows = [
        _usd_row(delivery_month="08/2026"),
        _usd_row(delivery_month="09/2026"),
        _usd_row(delivery_month="10/2026"),
    ]

    summary = await service.import_rows(
        rows=rows,
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.total_rows == 3
    assert summary.processed_rows == 3
    assert summary.failed_rows == 0
    assert summary.created_quote_count == 1
    assert summary.created_line_count == 3
    assert summary.failed_group_count == 0
    assert len(quote_service.calls) == 1
    assert len(quote_service.calls[0].lines_data) == 3
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_import_rows_matches_supplier_name_despite_case_and_whitespace() -> None:
    """The row's supplier_name has extra spacing/casing differences from what
    is stored in `Supplier.name`; grouping and resolution must still treat
    them as the same supplier (per the historical-file reality: files record
    display names, not catalog codes, so exact-string matching is too strict)."""
    supplier_id = uuid4()
    material_id = uuid4()
    session = FakeSession(
        suppliers=[(TAN_LONG_NAME, "TAN_LONG", supplier_id)],
        material_ids_by_code={"CORN": material_id},
    )
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    rows = [
        _usd_row(supplier_name="  tập đoàn   tân long (TAN LONG GROUP)  "),
        _usd_row(supplier_name="Tập đoàn Tân Long (Tan Long Group)", delivery_month="08/2026"),
    ]

    summary = await service.import_rows(
        rows=rows,
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.created_quote_count == 1
    assert summary.created_line_count == 2
    assert len(quote_service.calls) == 1
    assert quote_service.calls[0].supplier_id == supplier_id


@pytest.mark.asyncio
async def test_import_rows_ambiguous_supplier_name_fails_group() -> None:
    supplier_id_a = uuid4()
    supplier_id_b = uuid4()
    material_id = uuid4()
    session = FakeSession(
        suppliers=[
            (TAN_LONG_NAME, "TAN_LONG", supplier_id_a),
            (TAN_LONG_NAME, "TAN_LONG", supplier_id_b),
        ],
        material_ids_by_code={"CORN": material_id},
    )
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    summary = await service.import_rows(
        rows=[_usd_row()],
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.created_quote_count == 0
    assert summary.failed_group_count == 1
    assert quote_service.calls == []
    assert "khớp nhiều hơn một nhà cung cấp" in summary.errors[0]["errors"][0]


@pytest.mark.asyncio
async def test_import_rows_creates_separate_quotes_for_different_received_dates() -> None:
    supplier_id = uuid4()
    material_id = uuid4()
    session = FakeSession(
        suppliers=[(TAN_LONG_NAME, "TAN_LONG", supplier_id)],
        material_ids_by_code={"CORN": material_id},
    )
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    rows = [
        _usd_row(received_date="15/06/2026"),
        _usd_row(received_date="20/07/2026"),
    ]

    summary = await service.import_rows(
        rows=rows,
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.created_quote_count == 2
    assert summary.created_line_count == 2
    assert len(quote_service.calls) == 2


@pytest.mark.asyncio
async def test_import_rows_rejects_exact_duplicate_of_existing_line() -> None:
    """Re-importing a file whose row is byte-for-byte identical (NCC + ngày +
    vật tư + giá + kỳ giao...) to a line already in the system must be
    rejected with a clear error, not silently create a second quote — see
    docs/quotify/plan-import-bao-gia-cu.md quyết định "trùng hoàn toàn dữ
    liệu" ngày 12/08/2026."""
    supplier_id = uuid4()
    material_id = uuid4()
    existing_line = (
        supplier_id,
        date(2026, 6, 15),
        material_id,
        date(2026, 7, 1),
        "USD",
        "MT",
        Decimal("300.00"),
        Decimal("26100.00"),
        Decimal("5.00"),
        Decimal("200.00"),
    )
    session = FakeSession(
        suppliers=[(TAN_LONG_NAME, "TAN_LONG", supplier_id)],
        material_ids_by_code={"CORN": material_id},
        existing_lines=[existing_line],
    )
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    summary = await service.import_rows(
        rows=[_usd_row()],
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.created_quote_count == 0
    assert summary.failed_group_count == 1
    assert quote_service.calls == []
    assert "đã tồn tại trong hệ thống" in summary.errors[0]["errors"][0]


@pytest.mark.asyncio
async def test_import_rows_allows_second_quote_same_supplier_and_date_with_different_price() -> (
    None
):
    """Không chặn NCC báo giá 2 lần trong cùng ngày nếu dữ liệu dòng khác
    nhau (ví dụ giá khác) — chỉ chặn khi trùng hoàn toàn."""
    supplier_id = uuid4()
    material_id = uuid4()
    existing_line = (
        supplier_id,
        date(2026, 6, 15),
        material_id,
        date(2026, 7, 1),
        "USD",
        "MT",
        Decimal("310.00"),
        Decimal("26100.00"),
        Decimal("5.00"),
        Decimal("200.00"),
    )
    session = FakeSession(
        suppliers=[(TAN_LONG_NAME, "TAN_LONG", supplier_id)],
        material_ids_by_code={"CORN": material_id},
        existing_lines=[existing_line],
    )
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    summary = await service.import_rows(
        rows=[_usd_row()],
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.created_quote_count == 1
    assert summary.failed_group_count == 0
    assert len(quote_service.calls) == 1


@pytest.mark.asyncio
async def test_import_rows_row_level_parse_failure_does_not_touch_db() -> None:
    session = FakeSession(suppliers=[], material_ids_by_code={})
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    rows = [_usd_row(price_original="not-a-number")]

    summary = await service.import_rows(
        rows=rows,
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.total_rows == 1
    assert summary.failed_rows == 1
    assert summary.failed_group_count == 1
    assert summary.created_quote_count == 0
    assert quote_service.calls == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_import_rows_unknown_material_code_fails_whole_group() -> None:
    supplier_id = uuid4()
    session = FakeSession(
        suppliers=[(TAN_LONG_NAME, "TAN_LONG", supplier_id)],
        material_ids_by_code={},  # CORN unresolved
    )
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    rows = [_usd_row(delivery_month="08/2026"), _usd_row(delivery_month="09/2026")]

    summary = await service.import_rows(
        rows=rows,
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.processed_rows == 0
    assert summary.failed_rows == 2
    assert summary.failed_group_count == 1
    assert summary.created_quote_count == 0
    assert quote_service.calls == []
    assert "CORN" in summary.errors[0]["errors"][0]


@pytest.mark.asyncio
async def test_import_rows_one_failed_group_does_not_affect_other_groups() -> None:
    good_supplier_id = uuid4()
    bad_supplier_id = uuid4()
    material_id = uuid4()
    session = FakeSession(
        suppliers=[
            (TAN_LONG_NAME, "TAN_LONG", good_supplier_id),
            ("Nhà cung cấp lỗi", "BAD_SUPPLIER", bad_supplier_id),
        ],
        material_ids_by_code={"CORN": material_id},
    )
    quote_service = FakeQuoteService(fail_for_supplier_ids={bad_supplier_id})
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    rows = [
        _usd_row(supplier_name=TAN_LONG_NAME),
        _usd_row(supplier_name="Nhà cung cấp lỗi", received_date="16/06/2026"),
    ]

    summary = await service.import_rows(
        rows=rows,
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.created_quote_count == 1
    assert summary.failed_group_count == 1
    assert summary.processed_rows == 1
    assert summary.failed_rows == 1
    assert len(quote_service.calls) == 1
    assert quote_service.calls[0].supplier_id == good_supplier_id


@pytest.mark.asyncio
async def test_import_rows_commits_in_batches() -> None:
    from app.services import quote_backfill_import as module

    original_batch_size = module.COMMIT_BATCH_SIZE
    module.COMMIT_BATCH_SIZE = 2
    try:
        supplier_id = uuid4()
        material_id = uuid4()
        session = FakeSession(
            suppliers=[(TAN_LONG_NAME, "TAN_LONG", supplier_id)],
            material_ids_by_code={"CORN": material_id},
        )
        quote_service = FakeQuoteService()
        service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

        # 3 distinct received_dates => 3 separate groups/quotes.
        rows = [
            _usd_row(received_date="01/06/2026"),
            _usd_row(received_date="02/06/2026"),
            _usd_row(received_date="03/06/2026"),
        ]

        await service.import_rows(
            rows=rows,
            fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
            created_by_id=uuid4(),
        )

        # 2 groups committed in the first batch + 1 leftover group committed
        # at the end => 2 commits total, not 1 (per-job) or 3 (per-group).
        assert session.commit_count == 2
    finally:
        module.COMMIT_BATCH_SIZE = original_batch_size


@pytest.mark.asyncio
async def test_import_rows_returns_empty_summary_for_empty_file() -> None:
    session = FakeSession(suppliers=[], material_ids_by_code={})
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    summary = await service.import_rows(
        rows=[],
        fieldnames=QUOTE_BACKFILL_IMPORT_TEMPLATE_HEADERS,
        created_by_id=uuid4(),
    )

    assert summary.total_rows == 0
    assert summary.created_quote_count == 0
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_import_rows_rejects_invalid_header() -> None:
    session = FakeSession(suppliers=[], material_ids_by_code={})
    quote_service = FakeQuoteService()
    service = QuoteBackfillImportService(session, quote_service)  # type: ignore[arg-type]

    with pytest.raises(QuoteBackfillImportHeaderError):
        await service.import_rows(
            rows=[_usd_row()],
            fieldnames=("wrong", "headers"),
            created_by_id=uuid4(),
        )
