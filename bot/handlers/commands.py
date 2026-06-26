from __future__ import annotations

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.utils import backend_error_text, get_chat_id
from bot.services.backend_client import BackendClient


router = Router()


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активного сценария.")
        return

    await state.clear()
    await message.answer("Сценарий отменён.")


@router.message(Command("start"))
async def start_command(message: Message, backend: BackendClient) -> None:
    try:
        await get_chat_id(message, backend)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    await message.answer(
        "Привет! Я Telegram-интерфейс дипломного проекта "
        "«ИИ-ассистент для ревью кода».\n\n"
        "Помогаю разбирать pull request'ы, качество Python/Ansible-кода, "
        "рефакторинг, тесты, читаемость и поддерживаемость решений.\n\n"
        "Пишите вопрос обычным сообщением, используйте /ask для сценария с темами "
        "или /clear, чтобы очистить историю диалога."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "/start — создать чат и показать инструкцию\n"
        "/help — список команд\n"
        "/clear — очистить историю текущего чата\n"
        "/ask — задать вопрос через выбор темы\n"
        "/cancel — отменить активный сценарий"
    )


@router.message(Command("clear"))
async def clear_command(message: Message, backend: BackendClient) -> None:
    try:
        chat_id = await get_chat_id(message, backend)
        await backend.clear_messages(chat_id)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    await message.answer("История очищена.")
