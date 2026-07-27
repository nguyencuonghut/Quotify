from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import Supplier, User
from app.schemas import (
    SupplierContactResponse,
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierLookupResponse,
    SupplierMaterialResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)
from app.services import (
    AuditLogContext,
    AuditLogService,
    SupplierAdminService,
    SupplierAlreadyExistsError,
    SupplierDuplicateMaterialError,
    SupplierInUseError,
    SupplierMaterialUnavailableError,
    SupplierNotFoundError,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def get_supplier_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SupplierAdminService:
    return SupplierAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_supplier_response(supplier: Supplier) -> SupplierResponse:
    return SupplierResponse(
        id=supplier.id,
        code=supplier.code,
        name=supplier.name,
        supplier_type=supplier.supplier_type,  # type: ignore[arg-type]
        status=supplier.status,  # type: ignore[arg-type]
        tax_code=supplier.tax_code,
        address=supplier.address,
        note=supplier.note,
        contacts=[
            SupplierContactResponse.model_validate(contact)
            for contact in supplier.contacts
        ],
        materials=[
            SupplierMaterialResponse(
                material_id=supplier_material.material_id,
                material_code=supplier_material.material.code,
                material_name=supplier_material.material.name,
            )
            for supplier_material in supplier.supplier_materials
        ],
        created_at=supplier.created_at,
        updated_at=supplier.updated_at,
    )


def _supplier_snapshot(supplier: Supplier) -> dict[str, object]:
    material_codes = [
        supplier_material.material.code for supplier_material in supplier.supplier_materials
    ]
    material_names = [
        supplier_material.material.name for supplier_material in supplier.supplier_materials
    ]
    return {
        "code": supplier.code,
        "name": supplier.name,
        "supplier_type": supplier.supplier_type,
        "status": supplier.status,
        "tax_code": supplier.tax_code,
        "address": supplier.address,
        "note": supplier.note,
        "contact_count": len(supplier.contacts),
        "material_count": len(supplier.supplier_materials),
        "material_codes": material_codes,
        "material_names": material_names,
    }


def _supplier_change_metadata(
    *,
    old: dict[str, object] | None,
    new: Supplier,
) -> dict[str, object]:
    new_snapshot = _supplier_snapshot(new)
    labels = {
        "code": "Mã NCC",
        "name": "Tên NCC",
        "supplier_type": "Loại NCC",
        "status": "Trạng thái",
        "tax_code": "Mã số thuế",
        "address": "Địa chỉ",
        "note": "Ghi chú",
        "contact_count": "Số liên hệ",
        "material_codes": "Vật tư cung cấp",
    }
    changes: list[dict[str, object]] = []
    for field, label in labels.items():
        old_value = old.get(field) if old is not None else None
        new_value = new_snapshot[field]
        if old is None or old_value != new_value:
            changes.append(
                {
                    "field": field,
                    "label": label,
                    "old_value": old_value,
                    "new_value": new_value,
                },
            )
    return {
        **new_snapshot,
        "changes": changes,
    }


@router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    current_user: Annotated[User, Depends(require_permission("suppliers.read"))],
    supplier_admin_service: Annotated[SupplierAdminService, Depends(get_supplier_admin_service)],
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    supplier_type: Literal["domestic", "international"] | None = None,
    status_filter: Literal["active", "inactive"] | None = Query(default=None, alias="status"),
    sort_by: str = "code",
    sort_order: str = "asc",
) -> SupplierListResponse:
    items, total = await supplier_admin_service.list_suppliers(
        limit=limit,
        offset=offset,
        search=search,
        supplier_type=supplier_type,
        status=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return SupplierListResponse(
        items=[_build_supplier_response(item) for item in items],
        total=total,
    )


@router.get("/lookup", response_model=SupplierLookupResponse)
async def lookup_suppliers(
    current_user: Annotated[User, Depends(require_permission("suppliers.read"))],
    supplier_admin_service: Annotated[SupplierAdminService, Depends(get_supplier_admin_service)],
    material_id: UUID,
) -> SupplierLookupResponse:
    suppliers = await supplier_admin_service.lookup_suppliers_by_material(material_id)
    return SupplierLookupResponse(
        items=[_build_supplier_response(supplier) for supplier in suppliers],
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: UUID,
    current_user: Annotated[User, Depends(require_permission("suppliers.read"))],
    supplier_admin_service: Annotated[SupplierAdminService, Depends(get_supplier_admin_service)],
) -> SupplierResponse:
    try:
        return _build_supplier_response(
            await supplier_admin_service.get_supplier_by_id(supplier_id),
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    request: Request,
    payload: SupplierCreateRequest,
    current_user: Annotated[User, Depends(require_permission("suppliers.create"))],
    supplier_admin_service: Annotated[SupplierAdminService, Depends(get_supplier_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SupplierResponse:
    try:
        supplier = await supplier_admin_service.create_supplier(
            code=payload.code,
            name=payload.name,
            supplier_type=payload.supplier_type,
            status=payload.status,
            tax_code=payload.tax_code,
            address=payload.address,
            note=payload.note,
            contacts=payload.contacts,
            material_ids=payload.material_ids,
        )
        await audit_log_service.log_event(
            action="suppliers.supplier_created",
            entity_type="supplier",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(supplier.id),
                metadata_json=_supplier_change_metadata(old=None, new=supplier),
            ),
        )
        await session.commit()
        return _build_supplier_response(supplier)
    except SupplierAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (SupplierDuplicateMaterialError, SupplierMaterialUnavailableError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID,
    request: Request,
    payload: SupplierUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("suppliers.update"))],
    supplier_admin_service: Annotated[SupplierAdminService, Depends(get_supplier_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SupplierResponse:
    try:
        old_supplier = await supplier_admin_service.get_supplier_by_id(supplier_id)
        old_snapshot = _supplier_snapshot(old_supplier)
        supplier = await supplier_admin_service.update_supplier(
            supplier_id=supplier_id,
            code=payload.code,
            name=payload.name,
            supplier_type=payload.supplier_type,
            status=payload.status,
            tax_code=payload.tax_code,
            address=payload.address,
            note=payload.note,
            contacts=payload.contacts,
            material_ids=payload.material_ids,
        )
        await audit_log_service.log_event(
            action="suppliers.supplier_updated",
            entity_type="supplier",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(supplier.id),
                metadata_json=_supplier_change_metadata(old=old_snapshot, new=supplier),
            ),
        )
        await session.commit()
        return _build_supplier_response(supplier)
    except SupplierNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SupplierAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (SupplierDuplicateMaterialError, SupplierMaterialUnavailableError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("suppliers.delete"))],
    supplier_admin_service: Annotated[SupplierAdminService, Depends(get_supplier_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    try:
        supplier = await supplier_admin_service.get_supplier_by_id(supplier_id)
        metadata = _supplier_snapshot(supplier)
        await supplier_admin_service.delete_supplier(supplier_id)
        await audit_log_service.log_event(
            action="suppliers.supplier_deleted",
            entity_type="supplier",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(supplier_id),
                metadata_json=metadata,
            ),
        )
        await session.commit()
    except SupplierNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SupplierInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
