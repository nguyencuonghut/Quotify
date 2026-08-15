from __future__ import annotations

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from openpyxl import load_workbook

from app.services.quote_export_service import build_quote_export_workbook

BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _make_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "received_date": date(2026, 7, 29),
        "supplier_name": "Cargill Việt Nam",
        "material_name": "Ngô hạt",
        "price_original": Decimal("250.50"),
        "currency": "USD",
        "unit": "MT",
        "exchange_rate": Decimal("25450.00"),
        "delivery_month": date(2026, 8, 1),
        "import_tax_rate_percent": Decimal("5.00"),
        "processing_cost_vnd_per_kg": Decimal("150.00"),
        "price_converted_vnd_per_kg": Decimal("6525.23"),
        "purchased": True,
        "version_status": "confirmed",
        "note_content": "Đã thương lượng giảm giá 2%",
        "note_author_name": "Nguyễn Văn Mua",
        "note_created_at": datetime(2026, 7, 30, 3, 0, tzinfo=UTC),
    }
    row.update(overrides)
    return row


@pytest.fixture
def workbook_bytes() -> bytes:
    return build_quote_export_workbook(
        [_make_row()],
        generated_at=datetime(2026, 8, 15, 3, 0, tzinfo=UTC),
    )


def _load_sheet(workbook_bytes: bytes):
    workbook = load_workbook(io.BytesIO(workbook_bytes))
    return workbook, workbook.active


def test_returns_loadable_xlsx_with_business_sheet_name(workbook_bytes: bytes) -> None:
    workbook, sheet = _load_sheet(workbook_bytes)
    assert sheet.title == "Bảng báo giá"


def test_title_row_and_generated_timestamp_use_business_timezone(
    workbook_bytes: bytes,
) -> None:
    _, sheet = _load_sheet(workbook_bytes)

    assert "BÁO CÁO" in sheet["A1"].value
    # 2026-08-15T03:00:00Z -> 10:00 tại Asia/Ho_Chi_Minh (UTC+7)
    assert "15/08/2026" in sheet["A2"].value
    assert "10:00" in sheet["A2"].value
    assert "1" in sheet["A2"].value  # tổng số dòng


def test_writes_column_headers_in_expected_order(workbook_bytes: bytes) -> None:
    _, sheet = _load_sheet(workbook_bytes)
    header_row = [cell.value for cell in sheet[3]]

    assert header_row == [
        "Ngày nhận",
        "Nhà cung cấp",
        "Vật tư",
        "Giá gốc",
        "Đơn vị tính",
        "Tỷ giá",
        "Kỳ giao hàng",
        "Thuế NK (%)",
        "Chi phí làm hàng (VNĐ/KG)",
        "Giá quy đổi (VNĐ/KG)",
        "Chốt mua",
        "Trạng thái",
        "Ghi chú",
        "Người ghi chú",
        "Thời gian ghi chú",
    ]


def test_header_row_is_bold_white_text_on_a_dark_fill(workbook_bytes: bytes) -> None:
    _, sheet = _load_sheet(workbook_bytes)
    header_cell = sheet["A3"]

    assert header_cell.font.bold is True
    assert header_cell.font.color.rgb.endswith("FFFFFF")
    assert header_cell.fill.fgColor.rgb is not None
    assert header_cell.fill.fgColor.rgb != "00000000"


def test_writes_business_columns_for_a_single_row_with_correct_values(
    workbook_bytes: bytes,
) -> None:
    _, sheet = _load_sheet(workbook_bytes)
    data_row = [cell.value for cell in sheet[4]]

    # openpyxl round-trips number_format="dd/mm/yyyy" cells back as datetime
    # (not date) once the workbook is re-loaded from bytes.
    assert data_row[0] == datetime(2026, 7, 29)
    assert data_row[1] == "Cargill Việt Nam"
    assert data_row[2] == "Ngô hạt"
    assert data_row[3] == 250.5
    assert data_row[4] == "USD/MT"
    assert data_row[5] == 25450.0
    assert data_row[6] == datetime(2026, 8, 1)
    assert data_row[7] == 5.0
    assert data_row[8] == 150.0
    assert data_row[9] == 6525.23
    assert data_row[10] == "Đã chốt mua"
    assert data_row[11] == "Đã xác nhận"


def test_delivery_month_column_uses_a_month_year_format_not_a_full_date(
    workbook_bytes: bytes,
) -> None:
    # "Kỳ giao hàng" chỉ có ý nghĩa theo THÁNG (luôn là ngày 1 của tháng
    # trong DB) — hiện "dd/mm/yyyy" như received_date sẽ gây hiểu nhầm là có
    # ngày cụ thể trong tháng.
    _, sheet = _load_sheet(workbook_bytes)

    assert sheet["G4"].number_format == "mm/yyyy"
    assert sheet["A4"].number_format == "dd/mm/yyyy"


def test_shows_latest_note_content_author_and_local_timestamp_when_present(
    workbook_bytes: bytes,
) -> None:
    _, sheet = _load_sheet(workbook_bytes)
    data_row = [cell.value for cell in sheet[4]]

    assert data_row[12] == "Đã thương lượng giảm giá 2%"
    assert data_row[13] == "Nguyễn Văn Mua"
    # 2026-07-30T03:00:00Z -> 10:00 tại Asia/Ho_Chi_Minh
    assert data_row[14] == datetime(2026, 7, 30, 10, 0, tzinfo=BUSINESS_TIMEZONE).replace(
        tzinfo=None
    )


def test_strips_rich_text_html_markup_from_the_note_content() -> None:
    # Ghi chú lưu dạng HTML (soạn qua trình soạn thảo Quill trên frontend, xem
    # `note_content` thật lấy từ DB) — export phải hiện văn bản thuần, không
    # được để lộ thẻ HTML/entity thô như "<p>"/"&nbsp;" trong báo cáo.
    workbook_bytes = build_quote_export_workbook(
        [
            _make_row(
                note_content="<p>Giá&nbsp;đang&nbsp;có&nbsp;xu&nbsp;hướng&nbsp;tăng.&nbsp;Chờ&nbsp;tiếp</p>",
            )
        ],
        generated_at=datetime(2026, 8, 15, 3, 0, tzinfo=UTC),
    )
    _, sheet = _load_sheet(workbook_bytes)
    data_row = [cell.value for cell in sheet[4]]

    assert data_row[12] == "Giá đang có xu hướng tăng. Chờ tiếp"


def test_shows_blank_note_columns_when_the_quote_has_no_note() -> None:
    workbook_bytes = build_quote_export_workbook(
        [
            _make_row(
                note_content=None,
                note_author_name=None,
                note_created_at=None,
            )
        ],
        generated_at=datetime(2026, 8, 15, 3, 0, tzinfo=UTC),
    )
    _, sheet = _load_sheet(workbook_bytes)
    data_row = [cell.value for cell in sheet[4]]

    assert data_row[12] is None
    assert data_row[13] is None
    assert data_row[14] is None


def test_marks_unpurchased_lines_distinctly_from_purchased_ones() -> None:
    workbook_bytes = build_quote_export_workbook(
        [_make_row(purchased=False)],
        generated_at=datetime(2026, 8, 15, 3, 0, tzinfo=UTC),
    )
    _, sheet = _load_sheet(workbook_bytes)

    assert sheet["K4"].value == "Chưa chốt"


def test_enables_autofilter_and_freezes_the_header_row(workbook_bytes: bytes) -> None:
    _, sheet = _load_sheet(workbook_bytes)

    assert sheet.auto_filter.ref is not None
    assert sheet.freeze_panes == "A4"
