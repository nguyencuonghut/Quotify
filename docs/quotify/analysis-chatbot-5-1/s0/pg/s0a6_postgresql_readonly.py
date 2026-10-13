import asyncio, warnings, logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.exc import DBAPIError
from common import DSN

def desc(e):
    orig = getattr(e, "orig", None)
    cause = getattr(orig, "__cause__", None)
    return f"{type(e).__name__}/{type(cause).__name__}/SQLSTATE={getattr(cause,'sqlstate',None)}: {str(orig).strip().splitlines()[0] if orig else e}"

async def try_insert(c, label, id_):
    try:
        await c.execute(text(f"INSERT INTO ro_t VALUES ({id_}, '{label}')"))
        print(f"  [{label}] INSERT ACCEPTED (not read-only)")
        await c.rollback()
        return True
    except DBAPIError as e:
        print(f"  [{label}] INSERT rejected: {desc(e)}")
        await c.rollback()
        return False

async def main():
    logging.basicConfig()
    sql_log = logging.getLogger("sqlalchemy.engine")
    admin = create_async_engine(DSN, isolation_level="AUTOCOMMIT")
    async with admin.connect() as c:
        await c.execute(text("CREATE TABLE IF NOT EXISTS ro_t(id int primary key, v text)"))
    await admin.dispose()

    # Capture BEGIN statements the server sees: use pg log? Use asyncpg-level: SHOW inside txn instead.
    print("== A. engine.execution_options(postgresql_readonly=True), default isolation (READ COMMITTED)")
    base = create_async_engine(DSN, pool_size=1, max_overflow=0)
    ro_engine = base.execution_options(postgresql_readonly=True)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        async with ro_engine.connect() as c:
            print("  SHOW transaction_read_only:", (await c.execute(text("SHOW transaction_read_only"))).scalar(),
                  "| iso:", (await c.execute(text("SHOW transaction_isolation"))).scalar())
            await try_insert(c, "A-engine-opt", 101)
        print("  warnings raised:", [str(x.message) for x in w])

    print("== B. same engine, plain (non-OptionEngine) checkout afterwards: leak across pool?")
    async with base.connect() as c:
        print("  plain engine (shares pool) SHOW transaction_read_only:", (await c.execute(text("SHOW transaction_read_only"))).scalar())
        await try_insert(c, "B-plain-after", 102)

    print("== C. connection-level execution_options(postgresql_readonly=True) before first statement")
    async with base.connect() as c:
        c2 = await c.execution_options(postgresql_readonly=True)
        print("  SHOW transaction_read_only:", (await c2.execute(text("SHOW transaction_read_only"))).scalar())
        await try_insert(c2, "C-conn-opt", 103)
        await c2.rollback()

    print("== C2. after an autobegun statement (the 'only before txn' trap)")
    async with base.connect() as c:
        await c.execute(text("SELECT 1"))
        try:
            c2 = await c.execution_options(postgresql_readonly=True)
            print("  no error setting option mid-txn; SHOW:", (await c2.execute(text("SHOW transaction_read_only"))).scalar())
            await try_insert(c2, "C2-mid-txn", 104)
        except Exception as e:
            print("  ERROR setting option mid-txn:", type(e).__name__, str(e).splitlines()[0])
        await c.rollback()

    print("== D. leak check: plain engine connection after C (does pooled DBAPI connection keep readonly=True?)")
    async with base.connect() as c:
        print("  SHOW transaction_read_only:", (await c.execute(text("SHOW transaction_read_only"))).scalar())
        await c.rollback()

    print("== E. explicit isolation_level=SERIALIZABLE + readonly (docstring's supported case)")
    async with base.connect() as c:
        c2 = await c.execution_options(isolation_level="SERIALIZABLE", postgresql_readonly=True)
        print("  SHOW:", (await c2.execute(text("SHOW transaction_read_only"))).scalar(), (await c2.execute(text("SHOW transaction_isolation"))).scalar())
        await try_insert(c2, "E-serializable", 105)
    print("  after leaving: plain checkout:")
    async with base.connect() as c:
        print("  SHOW:", (await c.execute(text("SHOW transaction_read_only"))).scalar(), (await c.execute(text("SHOW transaction_isolation"))).scalar())

    print("== F. engine isolation_level='READ COMMITTED' explicit + postgresql_readonly (create_async_engine level)")
    e2 = create_async_engine(DSN, pool_size=1, max_overflow=0, isolation_level="READ COMMITTED").execution_options(postgresql_readonly=True)
    async with e2.connect() as c:
        print("  SHOW:", (await c.execute(text("SHOW transaction_read_only"))).scalar(), (await c.execute(text("SHOW transaction_isolation"))).scalar())
        await try_insert(c, "F-explicit-RC", 106)

    print("== G. AsyncSession + sessionmaker bound to ro_engine (the shape a tool would use)")
    sm = async_sessionmaker(ro_engine, expire_on_commit=False)
    async with sm() as s:
        print("  SHOW:", (await s.execute(text("SHOW transaction_read_only"))).scalar())
        try:
            await s.execute(text("INSERT INTO ro_t VALUES (107,'G')"))
            print("  [G] ACCEPTED")
        except DBAPIError as e:
            print("  [G] rejected:", desc(e))
        await s.rollback()
    print("== H. commit then re-use on ro_engine: still read-only in 2nd transaction?")
    async with ro_engine.connect() as c:
        await c.execute(text("SELECT 1")); await c.commit()
        print("  2nd txn SHOW:", (await c.execute(text("SHOW transaction_read_only"))).scalar())
        await c.rollback()
    await base.dispose(); await e2.dispose()

asyncio.run(main())
