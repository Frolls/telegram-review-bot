from __future__ import annotations

import httpx
from aiogram import F, Router
from aiogram.types import Message

from bot.handlers.utils import backend_error_text, get_chat_id, render_stream
from bot.services.backend_client import BackendClient


router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def text_message(message: Message, backend: BackendClient) -> None:
    if message.text is None:
        return

    try:
        chat_id = await get_chat_id(message, backend)
        response_message = await message.answer("...")
        await render_stream(response_message, backend.send_message(chat_id, message.text))
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
