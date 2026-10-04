"""Persistent agent commands and owner-bound approval buttons."""
from hashlib import sha256

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.utils import _send_message, backend_error_text, split_answer
from bot.services.backend_client import BackendClient

router = Router()
THREAD = "telegram-actions"


def approval_token(request_id: str) -> str:
    return sha256(request_id.encode()).hexdigest()[:24]


async def show_pending(message: Message, pending: dict) -> None:
    token = approval_token(pending["request_id"])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Подтвердить", callback_data=f"act:yes:{token}"),
        InlineKeyboardButton(text="Отменить", callback_data=f"act:no:{token}"),
    ]])
    for page in split_answer("Предлагаемое действие:\n" + pending["preview"]):
        await _send_message(message, page)
    await message.answer("Отправить это сообщение?", reply_markup=keyboard)


async def display_events(message: Message, backend: BackendClient, events: list[dict]):
    answer = ""
    for event in events:
        data = event.get("data") or {}
        if event.get("event") == "error":
            await message.answer(str(data.get("message", "Ошибка агента")))
            return
        if event.get("event") == "updates" and isinstance(data, dict):
            for update in data.values():
                if not isinstance(update, dict):
                    continue
                for result in update.get("tool_results", []):
                    text = f"Инструмент: {result['name']}\nРезультат: {result['result']}"
                    for page in split_answer(text):
                        await _send_message(message, page)
                for item in update.get("messages", []):
                    if isinstance(item, dict) and item.get("type") == "ai" and item.get("content") and not item.get("tool_calls"):
                        answer = str(item["content"])
    pending = await backend.pending_action()
    if pending:
        await show_pending(message, pending)
    elif answer:
        for page in split_answer(answer):
            await _send_message(message, page)
    else:
        await message.answer("Запуск завершён.")


@router.message(Command("agent"))
async def agent_command(message: Message, backend: BackendClient):
    question = (message.text or "").partition(" ")[2].strip()
    status = None
    try:
        pending = await backend.pending_action()
        if pending:
            await show_pending(message, pending)
            return
        if not question:
            await message.answer("Пример: /agent Который сейчас час в Asia/Yekaterinburg?\nДля действия: /agent Отправь мне сообщение: ревью завершено. Перед отправкой появятся кнопки подтверждения.")
            return
        status = await message.answer("⏳ Агент выполняет запрос…")
        content = f"Telegram ID инициатора: {message.from_user.id}. Запрос пользователя: {question}"
        events = await backend.agent({"thread_id": THREAD, "input": {"messages": [{"role": "user", "content": content}]}})
        await status.edit_text("Шаги агента:")
        await display_events(message, backend, events)
    except httpx.HTTPError as exc:
        error_text = backend_error_text(exc)
        if status is not None:
            await status.edit_text(error_text)
        else:
            await message.answer(error_text)


@router.callback_query(F.data.startswith("act:"))
async def approve_action(callback: CallbackQuery, backend: BackendClient):
    if not isinstance(callback.message, Message):
        return
    await callback.answer()
    try:
        _, decision, token = (callback.data or "").split(":", 2)
        pending = await backend.pending_action()
        if decision not in {"yes", "no"} or not pending or approval_token(pending["request_id"]) != token:
            await callback.message.answer("Это подтверждение устарело. Используйте /agent для текущего действия.")
            return
        events = await backend.agent({"thread_id": THREAD, "resume": decision == "yes", "request_id": pending["request_id"]})
        await callback.message.edit_reply_markup(reply_markup=None)
        await display_events(callback.message, backend, events)
    except httpx.HTTPError as exc:
        await callback.message.answer(backend_error_text(exc))
