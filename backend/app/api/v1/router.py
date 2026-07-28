from fastapi import APIRouter

from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.backups import router as backups_router
from app.api.v1.catalog_imports import router as catalog_imports_router
from app.api.v1.exchange_rates import router as exchange_rates_router
from app.api.v1.files import router as files_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.material_types import router as material_types_router
from app.api.v1.materials import router as materials_router
from app.api.v1.permissions import router as permissions_router
from app.api.v1.quotes import router as quotes_router
from app.api.v1.quotify_settings import router as quotify_settings_router
from app.api.v1.roles import router as roles_router
from app.api.v1.suppliers import router as suppliers_router
from app.api.v1.users import router as users_router

router = APIRouter()
router.include_router(audit_logs_router)
router.include_router(auth_router)
router.include_router(backups_router)
router.include_router(catalog_imports_router)
router.include_router(exchange_rates_router)
router.include_router(files_router)
router.include_router(health_router)
router.include_router(jobs_router)
router.include_router(material_types_router)
router.include_router(materials_router)
router.include_router(suppliers_router)
router.include_router(quotes_router)
router.include_router(permissions_router)
router.include_router(quotify_settings_router)
router.include_router(roles_router)
router.include_router(users_router)

