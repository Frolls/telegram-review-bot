from __future__ import annotations

from uuid import UUID

import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.handlers.utils import INTERFACE, backend_error_text
from bot.services.backend_client import BackendClient


router = Router()


@router.callback_query(F.data.startswith("fb:"))
async def feedback_callback(callback: CallbackQuery, backend: BackendClient) -> None:
    data = callback.data or ""
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[1] not in {"up", "down"}:
        await callback.answer("Неизвестный фидбек", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer("Не могу сохранить фидбек", show_alert=True)
        return

    vote = parts[1]
    try:
        message_id = UUID(parts[2])
    except ValueError:
        await callback.answer("Некорректный id сообщения", show_alert=True)
        return

    try:
        chat_id = await backend.get_or_create_chat(str(callback.from_user.id), INTERFACE)
        await backend.save_feedback(chat_id, message_id, vote)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await callback.answer(backend_error_text(error), show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Спасибо за оценку")
