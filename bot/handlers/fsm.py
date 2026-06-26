from __future__ import annotations

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.utils import backend_error_text, get_chat_id, render_stream
from bot.keyboards.inline import TOPICS, topics_kb
from bot.services.backend_client import BackendClient
from bot.states import AskFlow


router = Router()


@router.message(Command("ask"))
async def ask_command(message: Message, state: FSMContext) -> None:
    await state.set_state(AskFlow.waiting_for_topic)
    await message.answer("Выберите тему вопроса:", reply_markup=topics_kb())


@router.callback_query(AskFlow.waiting_for_topic, F.data.startswith("topic:"))
async def choose_topic(callback: CallbackQuery, state: FSMContext) -> None:
    data = callback.data or ""
    slug = data.removeprefix("topic:")

    if slug == "cancel":
        await state.clear()
        await callback.answer("Отменено")
        if callback.message is not None:
            await callback.message.edit_text("Сценарий отменён.")
        return

    topic = TOPICS.get(slug)
    if topic is None:
        await callback.answer("Неизвестная тема", show_alert=True)
        return

    await state.update_data(topic=topic)
    await state.set_state(AskFlow.waiting_for_question)
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text(f"Тема: {topic}\nНапишите вопрос.")


@router.message(AskFlow.waiting_for_question, F.text)
async def ask_question(message: Message, state: FSMContext, backend: BackendClient) -> None:
    if message.text is None:
        return

    data = await state.get_data()
    topic = str(data.get("topic", "Общий вопрос"))
    prompt = f"Тема: {topic}. Вопрос: {message.text}"

    try:
        chat_id = await get_chat_id(message, backend)
        response_message = await message.answer("...")
        await render_stream(response_message, backend.send_message(chat_id, prompt))
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    await state.clear()
