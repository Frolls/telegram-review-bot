from __future__ import annotations

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.utils import backend_error_text, get_chat_id
from bot.keyboards.reply import CANCEL_BUTTON, CLEAR_BUTTON, HELP_BUTTON, main_menu_kb
from bot.services.backend_client import BackendClient


router = Router()


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_BUTTON)
async def cancel_command(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активного сценария.", reply_markup=main_menu_kb())
        return

    await state.clear()
    await message.answer("Сценарий отменён.", reply_markup=main_menu_kb())


@router.message(Command("start"))
async def start_command(message: Message, backend: BackendClient) -> None:
    try:
        await get_chat_id(message, backend)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    await message.answer(
        "Привет! Я Telegram-интерфейс дипломного проекта "
        "«ИИ-ассистент для разработки и ревью кода».\n\n"
        "Помогаю разбираться в Python/Ansible-коде во время его написания и проверять изменения, "
        "рефакторинг, тесты, читаемость и поддерживаемость решений.\n\n"
        "Пишите вопрос обычным сообщением, используйте /ask для сценария с темами "
        "или /clear, чтобы очистить историю диалога.\nМожно приложить PY, YAML, DIFF, PDF/DOCX или текстовый файл.\n/agent — инструменты и отправка сообщения с подтверждением.",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("help"))
@router.message(F.text == HELP_BUTTON)
async def help_command(message: Message) -> None:
    await message.answer(
        "/start — создать чат и показать инструкцию\n"
        "/help — список команд\n"
        "/clear — очистить чат и агента, отменить ожидающую отправку\n"
        "/clear_agent — очистить только агента и ожидающую отправку\n"
        "/clear_chat — очистить только обычный диалог\n"
        "/escalate <вопрос> — зарегистрировать заявку\n"
        "/ticket <ID> — статус заявки\n"
        "/ask — задать вопрос через выбор темы\n"
        "/agent — инструменты и ожидающее подтверждения действие\n"
        "/cancel — отменить выбор темы; действие агента отменяется его кнопкой",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("clear"))
@router.message(F.text == CLEAR_BUTTON)
async def clear_command(message: Message, backend: BackendClient, state: FSMContext) -> None:
    try:
        chat_id = await get_chat_id(message, backend)
        await backend.clear_all_history(chat_id)
        await state.clear()
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    await message.answer("История чата и агента очищена. Ожидающая отправка отменена.", reply_markup=main_menu_kb())


@router.message(Command("clear_agent"))
async def clear_agent_command(message: Message, backend: BackendClient) -> None:
    try:
        await backend.clear_agent_history()
    except httpx.HTTPError as error:
        await message.answer(backend_error_text(error))
        return
    await message.answer("История агента очищена. Ожидающая отправка отменена.")


@router.message(Command("clear_chat"))
async def clear_chat_command(message: Message, backend: BackendClient) -> None:
    try:
        await backend.clear_messages(await get_chat_id(message, backend))
    except httpx.HTTPError as error:
        await message.answer(backend_error_text(error))
        return
    await message.answer("История обычного диалога очищена. Память агента доступна через /agent.")


@router.message(Command("escalate"))
async def escalate_command(message: Message, backend: BackendClient) -> None:
    question = (message.text or "").partition(" ")[2].strip()
    if not question:
        await message.answer("Укажите вопрос: /escalate <вопрос для проверки>.")
        return
    try:
        ticket = await backend.create_escalation(question)
    except httpx.HTTPError as error:
        await message.answer(backend_error_text(error))
        return
    await message.answer(f"Заявка {ticket['id']} сохранена. Статус: {ticket['status']}. Автоматическое уведомление специалиста пока не подключено.")


@router.message(Command("ticket"))
async def ticket_command(message: Message, backend: BackendClient) -> None:
    ticket_id = (message.text or "").partition(" ")[2].strip()
    if len(ticket_id) != 32 or any(c not in "0123456789abcdef" for c in ticket_id):
        await message.answer("Укажите ID заявки: /ticket <ID>.")
        return
    try:
        ticket = await backend.get_escalation(ticket_id)
    except httpx.HTTPError as error:
        await message.answer(backend_error_text(error))
        return
    await message.answer(f"Заявка {ticket['id']}: {ticket['status']}.")
