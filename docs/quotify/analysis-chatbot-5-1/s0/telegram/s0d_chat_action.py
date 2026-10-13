"""S0(d): hành vi sendChatAction với bot dev thật. Không in token, không in chat_id."""
import asyncio, os, time

from app.core.config import get_settings
from app.integrations.telegram import TelegramApiError, TelegramClient


def fmt(ms: float) -> str:
    return f"{ms:.0f} ms"


async def timed(client, payload):
    t = time.perf_counter()
    try:
        res = await client._call("sendChatAction", payload)
        return ("ok", res, (time.perf_counter() - t) * 1000)
    except TelegramApiError as exc:
        return ("api_error", f"{exc.error_code}: {exc.description}", (time.perf_counter() - t) * 1000)


async def main() -> None:
    chat_id = int(os.environ["S0D_CHAT_ID"])
    settings = get_settings()
    client = TelegramClient.from_settings(settings)
    try:
        me = await client.get_me()
        print("bot:", me.username)

        kind, res, ms = await timed(client, {"chat_id": chat_id, "action": "typing"})
        print("1. typing, chat hợp lệ ->", kind, res, fmt(ms))

        kind, res, ms = await timed(client, {"chat_id": chat_id, "action": "khong_hop_le"})
        print("2. action không hợp lệ ->", kind, res, fmt(ms))

        kind, res, ms = await timed(client, {"chat_id": 1, "action": "typing"})
        print("3. chat không tồn tại ->", kind, res, fmt(ms))

        print("4. chuỗi 6 lần cách nhau 4 giây (người dùng quan sát chỉ báo 'đang gõ')")
        t0 = time.perf_counter()
        for i in range(6):
            kind, res, ms = await timed(client, {"chat_id": chat_id, "action": "typing"})
            print(f"   lần {i+1} lúc +{time.perf_counter()-t0:4.1f}s ->", kind, res, fmt(ms))
            if i < 5:
                await asyncio.sleep(4)
        print("   kết thúc chuỗi lúc +%.1fs; sau đây KHÔNG gửi thêm" % (time.perf_counter() - t0))
    finally:
        await client.aclose()


asyncio.run(main())
