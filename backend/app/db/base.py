from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models import (  # noqa: F401,E402
    audit_log,
    export_job,
    file,
    import_job,
    material,
    material_type,
    permission,
    quote,
    quote_version,
    quote_line,
    quote_note,
    quote_note_revision,
    quotify_setting,
    refresh_token,
    role,
    supplier,
    supplier_contact,
    supplier_material,
    user,
)
