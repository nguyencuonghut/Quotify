from __future__ import annotations

import io
from typing import Annotated, Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission, get_current_user
from app.db.session import get_db_session
from app.models import Quote, QuoteLine, QuoteVersion, User
from app.schemas.quote import (
    QuoteCreateRequest,
    QuoteDraftUpdateRequest,
    QuoteLinePurchaseToggleRequest,
    QuoteLineResponse,
    QuoteResponse,
    QuoteVersionResponse,
)
from app.api.v1.exchange_rates import get_exchange_rate_service
from app.api.v1.quotify_settings import get_quotify_settings_service
from app.api.v1.files import get_file_admin_service
from app.services import (
    AuditLogContext,
    AuditLogService,
    ExchangeRateService,
    FileAdminService,
    FileMetadataNotFoundError,
    QuotifySettingsService,
)
from app.api.v1.quotify_settings import get_audit_log_service
from app.services.quote_pricing import QuotePricingService
from app.services.quote_service import QuoteService

router = APIRouter(prefix="/quotes", tags=["quotes"])


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
        created_by_id=version.created_by_id,
        confirmed_at=version.confirmed_at,
        confirmed_by_id=version.confirmed_by_id,
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
                "supplier_id": str(quote.supplier_id),
                "supplier_code": quote.supplier.code,
                "version_number": 1,
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
    try:
        version = await quote_service.create_version(
            quote_id=id,
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
        action="quotes.version_created",
        entity_type="quote_version",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(version.id),
            metadata_json={
                "quote_id": str(id),
                "version_number": version.version_number,
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
    try:
        version = await quote_service.update_draft(
            quote_id=id,
            version_id=version_id,
            received_date=payload.received_date,
            is_backfilled=payload.is_backfilled,
            backfill_reason=payload.backfill_reason,
            lines_data=[line.model_dump() for line in payload.lines],
            updated_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

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
            },
        ),
    )
    await session.commit()
    return _build_version_response(version)


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
    try:
        line = await quote_service.toggle_line_purchase(
            line_id=line_id,
            purchase=payload.purchase,
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
                await file_admin_service.delete_file(db_file.id)
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
        "Content-Disposition": f'{disposition}; filename="{sa.text(db_file.filename)}"' if not db_file.filename.isascii() else f'{disposition}; filename="{db_file.filename}"',
        "Content-Length": str(db_file.size_bytes),
    }
    # Fix filename for non-ascii using format fallback if needed or just simple header
    headers["Content-Disposition"] = f'{disposition}; filename="{db_file.filename}"'
    
    return StreamingResponse(
        stream_file(),
        media_type=db_file.content_type,
        headers=headers,
    )
