from __future__ import annotations

import asyncio
import logging

import httpx
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers import router
from bot.services.backend_client import BackendClient
from bot.web import build_api


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    backend = BackendClient(str(settings.backend_url), admin_token=settings.admin_token)
    dispatcher["backend"] = backend

    api = build_api(bot, settings.internal_token)
    server_config = uvicorn.Config(
        api,
        host="0.0.0.0",
        port=settings.bot_api_port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)

    broadcast_task = asyncio.create_task(poll_broadcasts(bot, backend))

    try:
        await asyncio.gather(dispatcher.start_polling(bot), server.serve())
    finally:
        broadcast_task.cancel()
        await asyncio.gather(broadcast_task, return_exceptions=True)
        await backend.aclose()
        await bot.session.close()


async def poll_broadcasts(bot: Bot, backend: BackendClient) -> None:
    while True:
        try:
            broadcasts = await backend.fetch_pending_broadcasts()
            for item in broadcasts:
                failed = 0
                for owner_external_id in item.owner_external_ids:
                    try:
                        await bot.send_message(chat_id=int(owner_external_id), text=item.message)
                    except Exception:
                        failed += 1
                if failed:
                    await backend.complete_broadcast(
                        item.id,
                        status="failed",
                        error=f"failed recipients: {failed}",
                    )
                else:
                    await backend.complete_broadcast(item.id, status="sent")
        except httpx.HTTPStatusError as error:
            if _is_postgres_required(error):
                logging.info("broadcast polling skipped: backend admin API requires Postgres")
            else:
                logging.exception("broadcast polling failed")
        except (httpx.ConnectError, httpx.ReadTimeout):
            logging.exception("broadcast polling failed")
        await asyncio.sleep(10)


def _is_postgres_required(error: httpx.HTTPStatusError) -> bool:
    try:
        payload = error.response.json()
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    detail = payload.get("detail")
    if isinstance(detail, dict) and detail.get("code") == "postgres_required":
        return True
    error_payload = payload.get("error")
    return isinstance(error_payload, dict) and error_payload.get("code") == "postgres_required"


if __name__ == "__main__":
    asyncio.run(main())
