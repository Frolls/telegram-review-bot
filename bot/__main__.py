from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers import router
from bot.services.backend_client import BackendClient


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    backend = BackendClient(str(settings.backend_url))
    dispatcher["backend"] = backend

    try:
        await dispatcher.start_polling(bot)
    finally:
        await backend.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
