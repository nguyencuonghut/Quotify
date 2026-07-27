from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models import (  # noqa: F401,E402
    audit_log,
    export_job,
    file,
    import_job,
    permission,
    refresh_token,
    role,
    user,
)
