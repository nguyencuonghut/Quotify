import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from common import DSN
async def main():
    e = create_async_engine(DSN)
    forms = {
      "plan-literal  'bot:chat:' || :chat_id          (int param)": ("SELECT hashtextextended('bot:chat:' || :c, 0)", 123456789012),
      "plan-literal  same, str param                  ": ("SELECT hashtextextended('bot:chat:' || :c, 0)", "123456789012"),
      "CAST(:c AS BIGINT) cast inside concat           ": ("SELECT hashtextextended('bot:chat:' || CAST(:c AS BIGINT), 0)", 123456789012),
      ":c::text                                        ": ("SELECT hashtextextended('bot:chat:' || :c::text, 0)", 123456789012),
      "CAST(:c AS TEXT) with int param                 ": ("SELECT hashtextextended('bot:chat:' || CAST(:c AS TEXT), 0)", 123456789012),
    }
    for k,(sql,v) in forms.items():
        async with e.connect() as c:
            try:
                r = (await c.execute(text(sql), {"c": v})).scalar()
                print("OK  ", k, "->", r)
            except Exception as ex:
                print("FAIL", k, "->", str(getattr(ex,'orig',ex)).splitlines()[0][:110])
    await e.dispose()
asyncio.run(main())
