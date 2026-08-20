"""Pydantic schemas package."""

from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.schemas.auth import AccessTokenResponse, CurrentUserResponse, LoginRequest
from app.schemas.exchange_rate import ExchangeRateResponse
from app.schemas.file import FileListResponse, FileResponse
from app.schemas.job import (
    ExportJobListResponse,
    ExportJobResponse,
    ImportJobListResponse,
    ImportJobResponse,
)
from app.schemas.material import (
    MaterialCreateRequest,
    MaterialListResponse,
    MaterialLookupResponse,
    MaterialResponse,
    MaterialUpdateRequest,
)
from app.schemas.material_type import (
    MaterialTypeCreateRequest,
    MaterialTypeListResponse,
    MaterialTypeLookupResponse,
    MaterialTypeResponse,
    MaterialTypeUpdateRequest,
)
from app.schemas.permission import PermissionResponse
from app.schemas.quotify_settings import (
    QuotifySettingsResponse,
    QuotifySettingsUpdateRequest,
)
from app.schemas.role import (
    RoleCreateRequest,
    RoleListResponse,
    RoleLookupResponse,
    RoleResponse,
    RoleUpdateRequest,
)
from app.schemas.supplier import (
    SupplierContactRequest,
    SupplierContactResponse,
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierLookupResponse,
    SupplierMaterialResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)
from app.schemas.user import (
    UserAvatarUploadResponse,
    UserCreateRequest,
    UserListResponse,
    UserPasswordChangeRequest,
    UserResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)

__all__ = [
    "AccessTokenResponse",
    "AuditLogListResponse",
    "AuditLogResponse",
    "CurrentUserResponse",
    "QuotifySettingsUpdateRequest",
    "ExchangeRateResponse",
    "LoginRequest",
    "MaterialCreateRequest",
    "MaterialListResponse",
    "MaterialLookupResponse",
    "MaterialResponse",
    "MaterialTypeCreateRequest",
    "MaterialTypeListResponse",
    "MaterialTypeLookupResponse",
    "MaterialTypeResponse",
    "MaterialTypeUpdateRequest",
    "MaterialUpdateRequest",
    "FileListResponse",
    "FileResponse",
    "ImportJobResponse",
    "ImportJobListResponse",
    "ExportJobResponse",
    "ExportJobListResponse",
    "PermissionResponse",
    "QuotifySettingsResponse",
    "RoleCreateRequest",
    "RoleListResponse",
    "RoleLookupResponse",
    "RoleResponse",
    "RoleUpdateRequest",
    "SupplierContactRequest",
    "SupplierContactResponse",
    "SupplierCreateRequest",
    "SupplierListResponse",
    "SupplierLookupResponse",
    "SupplierMaterialResponse",
    "SupplierResponse",
    "SupplierUpdateRequest",
    "UserAvatarUploadResponse",
    "UserCreateRequest",
    "UserListResponse",
    "UserPasswordChangeRequest",
    "UserResponse",
    "UserRoleUpdateRequest",
    "UserUpdateRequest",
]
