"""S0(d), phần quan sát bằng mắt: chỉ báo 'đang gõ' của Telegram. Không in token, không in chat_id."""
import asyncio
import os
import time
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.integrations.telegram import TelegramClient

VN = timezone(timedelta(hours=7))
COUNTDOWN = 60


def now() -> str:
    return datetime.now(VN).strftime("%H:%M:%S")


async def typing(client: TelegramClient, chat_id: int) -> None:
    await client._call("sendChatAction", {"chat_id": chat_id, "action": "typing"})


async def main() -> None:
    chat_id = int(os.environ["S0D_CHAT_ID"])
    client = TelegramClient.from_settings(get_settings())
    try:
        start = datetime.now(VN) + timedelta(seconds=COUNTDOWN)
        print(f"[{now()}] HẸN: PHA 1 bắt đầu lúc {start.strftime('%H:%M:%S')} (giờ Việt Nam). "
              "Hãy mở chat với @HHQuotifyBot.", flush=True)
        await asyncio.sleep(COUNTDOWN)

        t0 = time.monotonic()
        print(f"[{now()}] PHA 1: gửi 'đang gõ' 6 lần, cách nhau 4 giây "
              "(kỳ vọng: chỉ báo hiện LIÊN TỤC khoảng 27 giây)", flush=True)
        for i in range(6):
            await typing(client, chat_id)
            print(f"[{now()}] +{time.monotonic() - t0:4.1f}s  gửi lần {i + 1}/6", flush=True)
            if i < 5:
                await asyncio.sleep(4)

        print(f"[{now()}] PHA 2: NGỪNG gửi. Hãy xem chỉ báo tắt sau bao nhiêu giây "
              "(tài liệu Telegram nói khoảng 5 giây)", flush=True)
        await asyncio.sleep(15)

        print(f"[{now()}] PHA 3: gửi 'đang gõ' một lần, 3 giây sau gửi một tin thử "
              "(kỳ vọng: chỉ báo tắt NGAY khi tin tới)", flush=True)
        await typing(client, chat_id)
        await asyncio.sleep(3)
        await client.send_message(
            chat_id,
            "Tin thử S0: chỉ báo 'đang gõ' nên tắt ngay khi tin này đến.",
            parse_mode=None,
        )
        print(f"[{now()}] đã gửi tin thử. HẾT. Không gửi thêm gì nữa.", flush=True)
    finally:
        await client.aclose()


asyncio.run(main())
