from __future__ import annotations

import html
import io
import re
from collections.abc import Generator
from datetime import date
from typing import Annotated, Any, BinaryIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.exchange_rates import get_exchange_rate_service
from app.api.v1.files import get_file_admin_service
from app.api.v1.quotify_settings import get_audit_log_service, get_quotify_settings_service
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import has_role
from app.db.session import get_db_session
from app.models import Quote, QuoteLine, QuoteNoteRevision, QuoteVersion, User
from app.schemas.quote import (
    QuoteCreateRequest,
    QuoteDraftUpdateRequest,
    QuoteLinePurchaseToggleRequest,
    QuoteLineResponse,
    QuoteResponse,
    QuoteVersionResponse,
)
from app.schemas.quote_list import QuoteFlattenedResponse, QuoteListResponse
from app.schemas.quote_note import (
    QuoteNoteResponse,
    QuoteNoteRevisionResponse,
    QuoteNoteUpdateRequest,
)
from app.services import (
    AuditLogContext,
    AuditLogService,
    ExchangeRateService,
    FileAdminService,
    FileMetadataNotFoundError,
    QuotifySettingsService,
)
from app.services.quote_note_service import QuoteNoteService
from app.services.quote_pricing import QuotePricingService
from app.services.quote_query_service import QuoteQueryService
from app.services.quote_service import QuoteService

router = APIRouter(prefix="/quotes", tags=["quotes"])
QUOTE_OWNER_DENIED_DETAIL = "Bạn chỉ được thao tác trên phiếu báo giá do mình tạo."


def get_quote_pricing_service(
    exchange_rate_service: Annotated[ExchangeRateService, Depends(get_exchange_rate_service)],
    settings_service: Annotated[QuotifySettingsService, Depends(get_quotify_settings_service)],
) -> QuotePricingService:
    return QuotePricingService(
        exchange_rate_service=exchange_rate_service,
        settings_service=settings_service,
    )


def get_quote_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    pricing_service: Annotated[QuotePricingService, Depends(get_quote_pricing_service)],
) -> QuoteService:
    return QuoteService(session, pricing_service)


def get_quote_note_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteNoteService:
    return QuoteNoteService(session)


def get_quote_query_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteQueryService:
    return QuoteQueryService(session)


def _build_line_response(line: QuoteLine) -> QuoteLineResponse:
    return QuoteLineResponse(
        id=line.id,
        material_id=line.material_id,
        material_code=line.material.code,
        material_name=line.material.name,
        price_original=line.price_original,
        currency=line.currency,
        unit=line.unit,
        delivery_month=line.delivery_month,
        line_order=line.line_order,
        exchange_rate=line.exchange_rate,
        exchange_rate_source=line.exchange_rate_source,
        exchange_rate_source_mode=line.exchange_rate_source_mode,
        exchange_rate_entered_at=line.exchange_rate_entered_at,
        exchange_rate_manual_reason=line.exchange_rate_manual_reason,
        exchange_rate_actor_id=line.exchange_rate_actor_id,
        conversion_cost_vnd_per_kg=line.conversion_cost_vnd_per_kg,
        price_converted_vnd_per_kg=line.price_converted_vnd_per_kg,
        purchase_marked_at=line.purchase_marked_at,
        purchase_marked_by_id=line.purchase_marked_by_id,
    )


def _build_version_response(version: QuoteVersion) -> QuoteVersionResponse:
    return QuoteVersionResponse(
        id=version.id,
        quote_id=version.quote_id,
        version_number=version.version_number,
        received_date=version.received_date,
        status=version.status,
        file_id=version.file_id,
        is_backfilled=version.is_backfilled,
        backfill_reason=version.backfill_reason,
        correction_reason=version.correction_reason,
        created_by_id=version.created_by_id,
        confirmed_at=version.confirmed_at,
        confirmed_by_id=version.confirmed_by_id,
        superseded_at=version.superseded_at,
        superseded_by_id=version.superseded_by_id,
        superseded_by_version_id=version.superseded_by_version_id,
        created_at=version.created_at,
        updated_at=version.updated_at,
        lines=[_build_line_response(line) for line in version.lines],
    )


def _build_quote_response(quote: Quote) -> QuoteResponse:
    return QuoteResponse(
        id=quote.id,
        supplier_id=quote.supplier_id,
        supplier_name=quote.supplier.name,
        supplier_code=quote.supplier.code,
        created_by_id=quote.created_by_id,
        created_at=quote.created_at,
        updated_at=quote.updated_at,
        versions=[_build_version_response(v) for v in quote.versions],
    )


def _is_admin_user(user: User) -> bool:
    return has_role(user, "admin")


async def _ensure_quote_mutation_allowed(
    *,
    session: AsyncSession,
    quote_id: UUID,
    current_user: User,
) -> None:
    if _is_admin_user(current_user):
        return
    quote = await session.get(Quote, quote_id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiếu báo giá.",
        )
    if quote.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=QUOTE_OWNER_DENIED_DETAIL,
        )


async def _ensure_line_belongs_to_quote(
    *,
    session: AsyncSession,
    quote_id: UUID,
    line_id: UUID,
) -> QuoteLine:
    stmt = select(QuoteLine).options(selectinload(QuoteLine.version)).where(QuoteLine.id == line_id)
    line = (await session.execute(stmt)).scalar_one_or_none()
    if not line or not line.version or line.version.quote_id != quote_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy dòng báo giá.",
        )
    return line


async def _ensure_note_revision_belongs_to_quote(
    *,
    note_service: QuoteNoteService,
    quote_id: UUID,
    revision_id: UUID,
) -> None:
    note = await note_service.get_note_by_quote_id(quote_id)
    if not note or all(revision.id != revision_id for revision in note.revisions):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên bản ghi chú.",
        )


def _ensure_note_revision_author_allowed(
    *,
    revision: QuoteNoteRevision | None,
    current_user: User,
) -> None:
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên bản ghi chú.",
        )
    if _is_admin_user(current_user):
        return
    if revision.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn chỉ được sửa hoặc xóa ghi chú do chính mình tạo.",
        )


@router.get("", response_model=QuoteListResponse)
async def list_quotes(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    query_service: Annotated[QuoteQueryService, Depends(get_quote_query_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    _: Annotated[User, Depends(require_permission("quotes.read"))],
    global_search: str | None = None,
    material_type_id: UUID | None = None,
    material_id: UUID | None = None,
    supplier_id: UUID | None = None,
    created_by_id: UUID | None = None,
    received_date_start: date | None = None,
    received_date_end: date | None = None,
    delivery_month: date | None = None,
    currency: str | None = None,
    purchased: bool | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    items, total = await query_service.query_flattened_quotes(
        global_search=global_search,
        material_type_id=material_type_id,
        material_id=material_id,
        supplier_id=supplier_id,
        created_by_id=created_by_id,
        received_date_start=received_date_start,
        received_date_end=received_date_end,
        delivery_month=delivery_month,
        currency=currency,
        purchased=purchased,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    await audit_service.log_event(
        action="quotes.list_viewed",
        entity_type="quote",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
        ),
    )

    return QuoteListResponse(
        items=[QuoteFlattenedResponse.model_validate(item) for item in items],
        total=total,
    )


@router.post("", response_model=QuoteResponse)
async def create_quote(
    request: Request,
    payload: QuoteCreateRequest,
    current_user: Annotated[User, Depends(require_permission("quotes.create"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteResponse:
    try:
        quote = await quote_service.create_quote(
            supplier_id=payload.supplier_id,
            received_date=payload.received_date,
            is_backfilled=payload.is_backfilled,
            backfill_reason=payload.backfill_reason,
            lines_data=[line.model_dump() for line in payload.lines],
            created_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        action="quotes.quote_created",
        entity_type="quote",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(quote.id),
            metadata_json={
                "quote_id": str(quote.id),
                "supplier_id": str(quote.supplier_id),
                "supplier_code": quote.supplier.code,
                "version_number": 1,
                "received_date": str(quote.versions[0].received_date) if quote.versions else None,
                "is_backfilled": quote.versions[0].is_backfilled if quote.versions else False,
                "backfill_reason": quote.versions[0].backfill_reason if quote.versions else None,
                "lines": [
                    {
                        "material_id": str(line.material_id),
                        "material_code": line.material.code if line.material else None,
                        "material_name": line.material.name if line.material else None,
                        "price_original": float(line.price_original),
                        "currency": line.currency,
                        "unit": line.unit,
                        "delivery_month": str(line.delivery_month),
                        "exchange_rate": float(line.exchange_rate) if line.exchange_rate else None,
                    }
                    for line in (quote.versions[0].lines if quote.versions else [])
                ],
            },
        ),
    )
    await session.commit()
    return _build_quote_response(quote)


@router.get("/{id}", response_model=QuoteResponse)
async def get_quote(
    id: UUID,
    current_user: Annotated[User, Depends(require_permission("quotes.read"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
) -> QuoteResponse:
    quote = await quote_service.get_quote_by_id(id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiếu báo giá.",
        )
    return _build_quote_response(quote)


@router.post("/{id}/versions", response_model=QuoteVersionResponse)
async def create_version(
    id: UUID,
    request: Request,
    payload: QuoteDraftUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("quotes.update"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteVersionResponse:
    await _ensure_quote_mutation_allowed(
        session=session,
        quote_id=id,
        current_user=current_user,
    )
    try:
        version = await quote_service.create_version(
            quote_id=id,
            received_date=payload.received_date,
            is_backfilled=payload.is_backfilled,
            backfill_reason=payload.backfill_reason,
            lines_data=[line.model_dump() for line in payload.lines],
            created_by_id=current_user.id,
            correction_reason=payload.correction_reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        action="quotes.version_created",
        entity_type="quote_version",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(version.id),
            metadata_json={
                "quote_id": str(id),
                "version_number": version.version_number,
                "correction_reason": version.correction_reason,
            },
        ),
    )
    await session.commit()
    return _build_version_response(version)


@router.put("/{id}/versions/{version_id}/draft", response_model=QuoteVersionResponse)
async def update_draft(
    id: UUID,
    version_id: UUID,
    request: Request,
    payload: QuoteDraftUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("quotes.update"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteVersionResponse:
    await _ensure_quote_mutation_allowed(
        session=session,
        quote_id=id,
        current_user=current_user,
    )
    # Load old version snapshot for audit log
    old_stmt = (
        select(QuoteVersion)
        .options(selectinload(QuoteVersion.lines).selectinload(QuoteLine.material))
        .where(QuoteVersion.id == version_id, QuoteVersion.quote_id == id)
    )
    old_version = (await session.execute(old_stmt)).scalar_one_or_none()

    old_data = None
    if old_version:
        old_data = {
            "received_date": str(old_version.received_date),
            "is_backfilled": old_version.is_backfilled,
            "backfill_reason": old_version.backfill_reason,
            "correction_reason": old_version.correction_reason,
            "lines": [
                {
                    "material_id": str(line.material_id),
                    "material_code": line.material.code if line.material else None,
                    "material_name": line.material.name if line.material else None,
                    "price_original": float(line.price_original),
                    "currency": line.currency,
                    "unit": line.unit,
                    "delivery_month": str(line.delivery_month),
                    "exchange_rate": float(line.exchange_rate) if line.exchange_rate else None,
                }
                for line in old_version.lines
            ],
        }

    try:
        version = await quote_service.update_draft(
            quote_id=id,
            version_id=version_id,
            received_date=payload.received_date,
            is_backfilled=payload.is_backfilled,
            backfill_reason=payload.backfill_reason,
            correction_reason=payload.correction_reason,
            lines_data=[line.model_dump() for line in payload.lines],
            updated_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Calculate changes
    changes = {}
    if old_data:
        new_data = {
            "received_date": str(version.received_date),
            "is_backfilled": version.is_backfilled,
            "backfill_reason": version.backfill_reason,
            "correction_reason": version.correction_reason,
            "lines": [
                {
                    "material_id": str(line.material_id),
                    "material_code": line.material.code if line.material else None,
                    "material_name": line.material.name if line.material else None,
                    "price_original": float(line.price_original),
                    "currency": line.currency,
                    "unit": line.unit,
                    "delivery_month": str(line.delivery_month),
                    "exchange_rate": float(line.exchange_rate) if line.exchange_rate else None,
                }
                for line in version.lines
            ],
        }
        for key in ["received_date", "is_backfilled", "backfill_reason", "correction_reason"]:
            if old_data[key] != new_data[key]:
                changes[key] = {"old": old_data[key], "new": new_data[key]}
        if old_data["lines"] != new_data["lines"]:
            changes["lines"] = {"old": old_data["lines"], "new": new_data["lines"]}

    await audit_service.log_event(
        action="quotes.version_updated",
        entity_type="quote_version",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(version.id),
            metadata_json={
                "quote_id": str(id),
                "version_number": version.version_number,
                "changes": changes,
            },
        ),
    )
    await session.commit()
    return _build_version_response(version)


@router.post("/{id}/versions/{version_id}/confirm", response_model=QuoteVersionResponse)
async def confirm_version(
    id: UUID,
    version_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("quotes.update"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteVersionResponse:
    await _ensure_quote_mutation_allowed(
        session=session,
        quote_id=id,
        current_user=current_user,
    )
    try:
        version = await quote_service.confirm_version(
            quote_id=id,
            version_id=version_id,
            confirmed_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        action="quotes.version_confirmed",
        entity_type="quote_version",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(version.id),
            metadata_json={
                "quote_id": str(id),
                "version_number": version.version_number,
                "changes": {"status": {"old": "draft", "new": "confirmed"}},
            },
        ),
    )
    await session.commit()
    return _build_version_response(version)


@router.delete("/{id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft_version(
    id: UUID,
    version_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("quotes.update"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await _ensure_quote_mutation_allowed(
        session=session,
        quote_id=id,
        current_user=current_user,
    )
    try:
        result = await quote_service.delete_draft_version(
            quote_id=id,
            version_id=version_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    source_file_cleanup = "not_applicable"
    if result.file_id:
        source_file_cleanup = "deleted"
        try:
            await file_admin_service.delete_file(
                file_id=result.file_id,
                user_id=current_user.id,
                can_delete_all=True,
            )
        except FileMetadataNotFoundError:
            source_file_cleanup = "metadata_missing"

    await audit_service.log_event(
        action="quotes.version_deleted",
        entity_type="quote_version",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(version_id),
            metadata_json={
                "quote_id": str(id),
                "version_id": str(result.deleted_version_id),
                "version_number": result.version_number,
                "version_status": "draft",
                "received_date": result.received_date.isoformat(),
                "correction_reason": result.correction_reason,
                "line_count": result.line_count,
                "deleted_scope": result.deleted_scope,
                "deleted_quote": result.deleted_quote,
                "deleted_quote_id": str(result.deleted_quote_id)
                if result.deleted_quote_id
                else None,
                "source_file_id": str(result.file_id) if result.file_id else None,
                "source_file_cleanup": source_file_cleanup,
            },
        ),
    )
    await session.commit()


@router.put("/{id}/lines/{line_id}/purchase", response_model=QuoteLineResponse)
async def toggle_purchase(
    id: UUID,
    line_id: UUID,
    request: Request,
    payload: QuoteLinePurchaseToggleRequest,
    current_user: Annotated[User, Depends(require_permission("quotes.mark_purchased"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteLineResponse:
    await _ensure_quote_mutation_allowed(
        session=session,
        quote_id=id,
        current_user=current_user,
    )
    # Load old line state for audit log
    old_line = await _ensure_line_belongs_to_quote(
        session=session,
        quote_id=id,
        line_id=line_id,
    )
    old_purchase_marked_at = old_line.purchase_marked_at

    try:
        line = await quote_service.toggle_line_purchase(
            line_id=line_id,
            purchase=payload.purchase,
            purchase_date=payload.purchase_date,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    action_name = "quotes.purchase_marked" if payload.purchase else "quotes.purchase_unmarked"
    await audit_service.log_event(
        action=action_name,
        entity_type="quote_line",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(line.id),
            metadata_json={
                "quote_id": str(id),
                "material_id": str(line.material_id),
                "material_code": line.material.code if line.material else None,
                "material_name": line.material.name if line.material else None,
                "changes": {
                    "purchase_marked_at": {
                        "old": str(old_purchase_marked_at) if old_purchase_marked_at else None,
                        "new": str(line.purchase_marked_at) if line.purchase_marked_at else None,
                    }
                },
            },
        ),
    )
    await session.commit()
    return _build_line_response(line)


@router.post("/{id}/versions/{version_id}/source-file", response_model=QuoteVersionResponse)
async def upload_source_file(
    id: UUID,
    version_id: UUID,
    request: Request,
    file: UploadFile,
    current_user: Annotated[User, Depends(require_permission("quotes.update"))],
    quote_service: Annotated[QuoteService, Depends(get_quote_service)],
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuoteVersionResponse:
    await _ensure_quote_mutation_allowed(
        session=session,
        quote_id=id,
        current_user=current_user,
    )
    quote_version = await session.get(QuoteVersion, version_id)
    if not quote_version or quote_version.quote_id != id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên bản báo giá.",
        )
    if quote_version.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chỉ được đính kèm tệp tin cho bản nháp (draft).",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên tệp tin trống.",
        )

    file_size = file.size
    data_stream: io.BytesIO | BinaryIO
    if file_size is None or file_size <= 0:
        file_content = await file.read()
        file_size = len(file_content)
        data_stream = io.BytesIO(file_content)
    else:
        data_stream = file.file

    db_file = None
    try:
        db_file = await file_admin_service.upload_file(
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file_size,
            data_stream=data_stream,
            is_public=False,
            uploaded_by_id=current_user.id,
        )
        version = await quote_service.associate_source_file(
            quote_id=id,
            version_id=version_id,
            file_id=db_file.id,
        )
    except Exception as e:
        if db_file is not None:
            try:
                await file_admin_service.delete_file(
                    file_id=db_file.id,
                    user_id=current_user.id,
                    can_delete_all=True,
                )
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể đính kèm tệp tin gốc báo giá: {e}",
        ) from e

    await audit_service.log_event(
        action="quotes.source_file_uploaded",
        entity_type="quote_version",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(version.id),
            metadata_json={
                "quote_id": str(id),
                "file_id": str(db_file.id),
                "filename": db_file.filename,
            },
        ),
    )
    await session.commit()
    return _build_version_response(version)


@router.get("/{id}/versions/{version_id}/source-file")
async def download_source_file(
    id: UUID,
    version_id: UUID,
    current_user: Annotated[User, Depends(require_permission("quotes.read"))],
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    inline: bool = False,
) -> StreamingResponse:
    quote_version = await session.get(QuoteVersion, version_id)
    if not quote_version or quote_version.quote_id != id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên bản báo giá.",
        )
    if not quote_version.file_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên bản báo giá chưa đính kèm tệp tin gốc.",
        )

    try:
        db_file = await file_admin_service.get_file_by_id(quote_version.file_id)
    except FileMetadataNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy metadata tệp tin.",
        ) from e

    try:
        minio_response = file_admin_service.minio_client.get_object(
            bucket_name=db_file.bucket,
            object_name=db_file.storage_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể tải tệp tin từ MinIO: {e}",
        ) from e

    def stream_file() -> Generator[bytes, None, None]:
        try:
            while chunk := minio_response.read(32 * 1024):
                yield chunk
        finally:
            minio_response.close()
            minio_response.release_conn()

    disposition = "inline" if inline else "attachment"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{db_file.filename}"',
        "Content-Length": str(db_file.size_bytes),
    }

    return StreamingResponse(
        stream_file(),
        media_type=db_file.content_type,
        headers=headers,
    )


@router.get("/{quote_id}/notes", response_model=QuoteNoteResponse)
async def get_quote_note(
    quote_id: UUID,
    note_service: Annotated[QuoteNoteService, Depends(get_quote_note_service)],
    _: Annotated[User, Depends(require_permission("quote_notes.read"))],
) -> Any:
    note = await note_service.get_note_by_quote_id(quote_id)
    if not note:
        return QuoteNoteResponse(
            id=None,
            quote_id=quote_id,
            created_at=None,
            updated_at=None,
            revisions=[],
        )

    revisions = []
    for r in note.revisions:
        revisions.append(
            QuoteNoteRevisionResponse(
                id=r.id,
                revision_number=r.revision_number,
                content=r.content,
                author_id=r.author_id,
                author_name=r.author.full_name if r.author else None,
                created_at=r.created_at,
            )
        )

    return QuoteNoteResponse(
        id=note.id,
        quote_id=note.quote_id,
        created_at=note.created_at,
        updated_at=note.updated_at,
        revisions=revisions,
    )


def clean_html_to_text(text: str | None) -> str | None:
    if not text:
        return text
    text = re.sub(r"</?(p|br|div|li)[^>]*>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return " ".join(text.split())


@router.put("/{quote_id}/notes", response_model=QuoteNoteRevisionResponse)
async def update_quote_note(
    request: Request,
    quote_id: UUID,
    body: QuoteNoteUpdateRequest,
    note_service: Annotated[QuoteNoteService, Depends(get_quote_note_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("quote_notes.create"))],
) -> Any:
    old_content = None
    note = await note_service.get_note_by_quote_id(quote_id)
    if note:
        last_revision = max(
            note.revisions, key=lambda revision: revision.revision_number, default=None
        )
        old_content = last_revision.content if last_revision else None

    try:
        revision = await note_service.update_note(
            quote_id=quote_id,
            content=body.content,
            author_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    # Log audit event
    await audit_service.log_event(
        action="quotes.note_updated",
        entity_type="quote",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(quote_id),
            metadata_json={
                "quote_id": str(quote_id),
                "revision_number": revision.revision_number,
                "changes": {
                    "content": {
                        "old": clean_html_to_text(old_content),
                        "new": clean_html_to_text(revision.content),
                    }
                },
            },
        ),
    )

    await session.commit()

    return QuoteNoteRevisionResponse(
        id=revision.id,
        revision_number=revision.revision_number,
        content=revision.content,
        author_id=revision.author_id,
        author_name=current_user.full_name,
        created_at=revision.created_at,
    )


@router.patch("/{quote_id}/notes/revisions/{revision_id}", response_model=QuoteNoteRevisionResponse)
async def update_note_revision(
    request: Request,
    quote_id: UUID,
    revision_id: UUID,
    body: QuoteNoteUpdateRequest,
    note_service: Annotated[QuoteNoteService, Depends(get_quote_note_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("quote_notes.update"))],
) -> Any:
    await _ensure_note_revision_belongs_to_quote(
        note_service=note_service,
        quote_id=quote_id,
        revision_id=revision_id,
    )
    old_rev = await note_service.get_revision_by_id(revision_id)
    _ensure_note_revision_author_allowed(revision=old_rev, current_user=current_user)
    old_content = old_rev.content if old_rev else None

    try:
        revision = await note_service.update_revision(
            revision_id=revision_id,
            content=body.content,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    # Log audit event
    await audit_service.log_event(
        action="quotes.note_revision_updated",
        entity_type="quote",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(quote_id),
            metadata_json={
                "quote_id": str(quote_id),
                "revision_id": str(revision_id),
                "revision_number": revision.revision_number,
                "changes": {
                    "content": {
                        "old": clean_html_to_text(old_content),
                        "new": clean_html_to_text(revision.content),
                    }
                },
            },
        ),
    )
    await session.commit()

    return QuoteNoteRevisionResponse(
        id=revision.id,
        revision_number=revision.revision_number,
        content=revision.content,
        author_id=revision.author_id,
        author_name=revision.author.full_name if revision.author else "Hệ thống",
        created_at=revision.created_at,
    )


@router.delete("/{quote_id}/notes/revisions/{revision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note_revision(
    request: Request,
    quote_id: UUID,
    revision_id: UUID,
    note_service: Annotated[QuoteNoteService, Depends(get_quote_note_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("quote_notes.update"))],
) -> None:
    await _ensure_note_revision_belongs_to_quote(
        note_service=note_service,
        quote_id=quote_id,
        revision_id=revision_id,
    )
    old_rev = await note_service.get_revision_by_id(revision_id)
    _ensure_note_revision_author_allowed(revision=old_rev, current_user=current_user)
    old_content = old_rev.content if old_rev else None
    old_revision_number = old_rev.revision_number if old_rev else None

    try:
        await note_service.delete_revision(revision_id=revision_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    # Log audit event
    await audit_service.log_event(
        action="quotes.note_revision_deleted",
        entity_type="quote",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(quote_id),
            metadata_json={
                "quote_id": str(quote_id),
                "revision_id": str(revision_id),
                "revision_number": old_revision_number,
                "content": clean_html_to_text(old_content),
            },
        ),
    )
    await session.commit()
