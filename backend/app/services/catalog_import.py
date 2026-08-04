from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.models import Material, MaterialType, Supplier, SupplierContact, SupplierMaterial
from app.schemas.supplier import normalize_supplier_types
from app.services.material_type_admin import normalize_catalog_code, normalize_optional_text

CatalogImportEntityType = Literal["material_types", "materials", "suppliers"]

CATALOG_IMPORT_ENTITY_TYPES: tuple[CatalogImportEntityType, ...] = (
    "material_types",
    "materials",
    "suppliers",
)


@dataclass(slots=True, frozen=True)
class CatalogImportConfig:
    entity_type: CatalogImportEntityType
    permission: str
    task_name: str
    template_filename: str
    template_headers: tuple[str, ...]
    sample_row: tuple[str, ...]
    started_action: str
    completed_action: str
    failed_action: str


CATALOG_IMPORT_CONFIGS: dict[str, CatalogImportConfig] = {
    "material_types": CatalogImportConfig(
        entity_type="material_types",
        permission="material_types.import",
        task_name="import_catalog_task",
        template_filename="material_types_import_template.csv",
        template_headers=("code", "name", "status", "note"),
        sample_row=("NGUYEN_LIEU", "Nguyên liệu", "active", "Ghi chú tùy chọn"),
        started_action="catalog.material_types_import_started",
        completed_action="catalog.material_types_import_completed",
        failed_action="catalog.material_types_import_failed",
    ),
    "materials": CatalogImportConfig(
        entity_type="materials",
        permission="materials.import",
        task_name="import_catalog_task",
        template_filename="materials_import_template.csv",
        template_headers=("code", "name", "material_type_code", "status", "note"),
        sample_row=("CORN", "Ngô hạt", "NGUYEN_LIEU", "active", "Ghi chú tùy chọn"),
        started_action="catalog.materials_import_started",
        completed_action="catalog.materials_import_completed",
        failed_action="catalog.materials_import_failed",
    ),
    "suppliers": CatalogImportConfig(
        entity_type="suppliers",
        permission="suppliers.import",
        task_name="import_catalog_task",
        template_filename="suppliers_import_template.csv",
        template_headers=(
            "code",
            "name",
            "supplier_type",
            "status",
            "tax_code",
            "address",
            "note",
            "contact_name",
            "contact_title",
            "contact_email",
            "contact_phone",
            "contact_status",
            "material_codes",
        ),
        sample_row=(
            "SUP-01",
            "Nhà cung cấp A",
            "domestic,international",
            "active",
            "0100000000",
            "Hà Nội",
            "Ghi chú tùy chọn",
            "Nguyễn Văn A",
            "Sales",
            "sales@example.com",
            "0900000000",
            "active",
            "CORN;SOYBEAN_MEAL",
        ),
        started_action="catalog.suppliers_import_started",
        completed_action="catalog.suppliers_import_completed",
        failed_action="catalog.suppliers_import_failed",
    ),
}


@dataclass(slots=True)
class CatalogImportSummary:
    total_rows: int = 0
    processed_rows: int = 0
    failed_rows: int = 0
    created_rows: int = 0
    updated_rows: int = 0
    errors: list[dict[str, object]] = field(default_factory=list)


class CatalogImportHeaderError(Exception):
    """Raised when a catalog import CSV has invalid headers."""


class CatalogImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_rows(
        self,
        *,
        entity_type: CatalogImportEntityType,
        rows: Iterable[dict[str, str | None]],
        fieldnames: Sequence[str] | None,
    ) -> CatalogImportSummary:
        config = get_catalog_import_config(entity_type)
        validate_catalog_import_headers(config, fieldnames)

        summary = CatalogImportSummary()
        for row_number, row in enumerate(rows, start=1):
            summary.total_rows = row_number
            try:
                async with self.session.begin_nested():
                    created = await self._upsert_row(config.entity_type, row)
            except Exception as exc:  # noqa: BLE001
                summary.failed_rows += 1
                summary.errors.append(
                    {
                        "row": row_number,
                        "code": normalize_optional_text(row.get("code")),
                        "errors": [str(exc)],
                    },
                )
            else:
                summary.processed_rows += 1
                if created:
                    summary.created_rows += 1
                else:
                    summary.updated_rows += 1

        return summary

    async def _upsert_row(
        self,
        entity_type: CatalogImportEntityType,
        row: dict[str, str | None],
    ) -> bool:
        if entity_type == "material_types":
            return await self._upsert_material_type(row)
        if entity_type == "materials":
            return await self._upsert_material(row)
        return await self._upsert_supplier(row)

    async def _upsert_material_type(self, row: dict[str, str | None]) -> bool:
        code = require_text(row, "code", "Mã loại vật tư")
        name = require_text(row, "name", "Tên loại vật tư")
        status = normalize_status(row.get("status"))
        note = normalize_optional_text(row.get("note"))

        material_type = await self._get_material_type_by_code(code)
        if material_type is None:
            self.session.add(
                MaterialType(
                    code=normalize_catalog_code(code),
                    name=name,
                    status=status,
                    note=note,
                ),
            )
            await self.session.flush()
            return True

        material_type.name = name
        material_type.status = status
        material_type.note = note
        await self.session.flush()
        return False

    async def _upsert_material(self, row: dict[str, str | None]) -> bool:
        code = require_text(row, "code", "Mã vật tư")
        name = require_text(row, "name", "Tên vật tư")
        material_type_code = require_text(row, "material_type_code", "Mã loại vật tư")
        status = normalize_status(row.get("status"))
        note = normalize_optional_text(row.get("note"))

        material_type = await self._get_material_type_by_code(material_type_code)
        if material_type is None:
            normalized_type_code = normalize_catalog_code(material_type_code)
            raise ValueError(f"Loại vật tư '{normalized_type_code}' không tồn tại.")

        material = await self._get_material_by_code(code)
        if material is None:
            self.session.add(
                Material(
                    code=normalize_catalog_code(code),
                    name=name,
                    material_type_id=material_type.id,
                    status=status,
                    note=note,
                ),
            )
            await self.session.flush()
            return True

        material.name = name
        material.material_type_id = material_type.id
        material.status = status
        material.note = note
        await self.session.flush()
        return False

    async def _upsert_supplier(self, row: dict[str, str | None]) -> bool:
        code = require_text(row, "code", "Mã NCC")
        name = require_text(row, "name", "Tên NCC")
        supplier_type = normalize_supplier_type(row.get("supplier_type"))
        status = normalize_status(row.get("status"))
        material_codes = parse_code_list(row.get("material_codes"))
        materials = await self._get_active_materials_by_codes(material_codes)

        supplier = await self._get_supplier_by_code(code)
        created = supplier is None
        if supplier is None:
            supplier = Supplier(code=normalize_catalog_code(code), name=name)
            set_committed_value(supplier, "contacts", [])
            set_committed_value(supplier, "supplier_materials", [])
            self.session.add(supplier)

        supplier.name = name
        supplier.supplier_type = supplier_type
        supplier.status = status
        supplier.tax_code = normalize_optional_text(row.get("tax_code"))
        supplier.address = normalize_optional_text(row.get("address"))
        supplier.note = normalize_optional_text(row.get("note"))
        supplier.contacts = build_supplier_contacts_from_row(row)
        supplier.supplier_materials = [
            SupplierMaterial(material_id=material.id) for material in materials
        ]
        await self.session.flush()
        return created

    async def _get_material_type_by_code(self, code: str) -> MaterialType | None:
        result = await self.session.execute(
            select(MaterialType).where(MaterialType.code == normalize_catalog_code(code)),
        )
        return result.scalar_one_or_none()

    async def _get_material_by_code(self, code: str) -> Material | None:
        result = await self.session.execute(
            select(Material).where(Material.code == normalize_catalog_code(code)),
        )
        return result.scalar_one_or_none()

    async def _get_supplier_by_code(self, code: str) -> Supplier | None:
        result = await self.session.execute(
            select(Supplier)
            .where(Supplier.code == normalize_catalog_code(code))
            .options(
                selectinload(Supplier.contacts),
                selectinload(Supplier.supplier_materials),
            ),
        )
        return result.scalar_one_or_none()

    async def _get_active_materials_by_codes(self, codes: Sequence[str]) -> Sequence[Material]:
        if not codes:
            return []

        normalized_codes = [normalize_catalog_code(code) for code in codes]
        result = await self.session.execute(
            select(Material).where(
                Material.code.in_(normalized_codes),
                Material.status == "active",
            ),
        )
        materials = result.scalars().all()
        found_codes = {material.code for material in materials}
        missing_codes = [code for code in normalized_codes if code not in found_codes]
        if missing_codes:
            raise ValueError(f"Vật tư không tồn tại hoặc inactive: {', '.join(missing_codes)}.")
        return materials


def get_catalog_import_config(entity_type: str) -> CatalogImportConfig:
    config = CATALOG_IMPORT_CONFIGS.get(entity_type)
    if config is None:
        allowed = ", ".join(CATALOG_IMPORT_ENTITY_TYPES)
        raise ValueError(f"Loại import không hợp lệ. Chỉ hỗ trợ: {allowed}.")
    return config


def build_catalog_import_template(config: CatalogImportConfig) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(config.template_headers)
    writer.writerow(config.sample_row)
    return buffer.getvalue().encode("utf-8-sig")


def build_catalog_import_error_report(job_errors: list[Any] | None) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "code", "errors"])
    for item in job_errors or []:
        if not isinstance(item, dict):
            continue
        errors = item.get("errors")
        if isinstance(errors, list):
            error_text = "; ".join(str(error) for error in errors)
        else:
            error_text = str(errors or "")
        writer.writerow([item.get("row", ""), item.get("code", ""), error_text])
    return buffer.getvalue().encode("utf-8-sig")


def validate_catalog_import_headers(
    config: CatalogImportConfig,
    fieldnames: Sequence[str] | None,
) -> None:
    received_headers = tuple(fieldnames or ())
    if received_headers != config.template_headers:
        expected = ", ".join(config.template_headers)
        received = ", ".join(received_headers) if received_headers else "(không có header)"
        raise CatalogImportHeaderError(
            f"Header CSV không hợp lệ. Cần: {expected}. Nhận: {received}.",
        )


def require_text(row: dict[str, str | None], key: str, label: str) -> str:
    value = normalize_optional_text(row.get(key))
    if value is None:
        raise ValueError(f"{label} là bắt buộc.")
    return value


def normalize_status(value: str | None) -> str:
    normalized = normalize_optional_text(value) or "active"
    normalized = normalized.lower()
    if normalized not in {"active", "inactive"}:
        raise ValueError("Trạng thái chỉ nhận active hoặc inactive.")
    return normalized


def normalize_supplier_type(value: str | None) -> str:
    normalized = normalize_optional_text(value)
    if normalized is None:
        raise ValueError("Loại NCC là bắt buộc.")
    return normalize_supplier_types(
        [
            part
            for part in re.split(r"[;,]", normalized.lower())
            if normalize_optional_text(part) is not None
        ],
    )


def parse_code_list(value: str | None) -> list[str]:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return []
    return [
        normalize_catalog_code(part)
        for part in re.split(r"[;,]", normalized)
        if normalize_optional_text(part) is not None
    ]


def build_supplier_contacts_from_row(row: dict[str, str | None]) -> list[SupplierContact]:
    contact_name = normalize_optional_text(row.get("contact_name"))
    if contact_name is None:
        return []
    return [
        SupplierContact(
            name=contact_name,
            title=normalize_optional_text(row.get("contact_title")),
            email=normalize_optional_text(row.get("contact_email")),
            phone=normalize_optional_text(row.get("contact_phone")),
            status=normalize_status(row.get("contact_status")),
        ),
    ]
