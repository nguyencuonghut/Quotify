"""Pydantic schemas package."""

from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.schemas.auth import AccessTokenResponse, CurrentUserResponse, LoginRequest
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
    MaterialResponse,
    MaterialUpdateRequest,
)
from app.schemas.material_type import (
    MaterialTypeCreateRequest,
    MaterialTypeListResponse,
    MaterialTypeResponse,
    MaterialTypeUpdateRequest,
)
from app.schemas.permission import PermissionResponse
from app.schemas.role import (
    RoleCreateRequest,
    RoleListResponse,
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
    UserResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)

__all__ = [
    "AccessTokenResponse",
    "AuditLogListResponse",
    "AuditLogResponse",
    "CurrentUserResponse",
    "LoginRequest",
    "MaterialCreateRequest",
    "MaterialListResponse",
    "MaterialResponse",
    "MaterialTypeCreateRequest",
    "MaterialTypeListResponse",
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
    "RoleCreateRequest",
    "RoleListResponse",
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
    "UserResponse",
    "UserRoleUpdateRequest",
    "UserUpdateRequest",
]
