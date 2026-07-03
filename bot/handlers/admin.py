from __future__ import annotations

import html

import httpx
from aiogram import Router
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import Message

from bot.handlers.utils import backend_error_text
from bot.services.backend_client import BackendClient


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        from bot.config import settings

        return message.from_user is not None and message.from_user.id in settings.bot_admin_ids


admin_router = Router()
admin_router.message.filter(IsAdmin())


@admin_router.message(Command("stats"))
async def stats_command(message: Message, backend: BackendClient) -> None:
    try:
        stats = await backend.admin_stats()
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    lines = ["<b>Stats за 24ч</b>"]
    for key in (
        "total_messages",
        "active_users",
        "avg_latency_ms",
        "moderation_block_rate",
        "feedback_up_ratio",
    ):
        lines.append(f"{html.escape(key)}: <code>{html.escape(str(stats.get(key, 0)))}</code>")
    top_questions = stats.get("top_questions") or []
    if top_questions:
        lines.append("")
        lines.append("<b>Топ вопросов</b>")
        for item in top_questions:
            question = html.escape(str(item.get("question", "")))[:120]
            count = html.escape(str(item.get("count", 0)))
            lines.append(f"{count} × {question}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@admin_router.message(Command("users"))
async def users_command(message: Message, backend: BackendClient) -> None:
    try:
        users = await backend.admin_users(limit=50)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    rows = ["owner_external_id | chats | last_seen_at"]
    for user in users[:10]:
        rows.append(
            f"{user.get('owner_external_id')} | "
            f"{user.get('chat_count')} | "
            f"{user.get('last_seen_at')}"
        )
    await message.answer(f"<pre>{html.escape(chr(10).join(rows))}</pre>", parse_mode="HTML")


@admin_router.message(Command("broadcast"))
async def broadcast_command(
    message: Message,
    command: CommandObject,
    backend: BackendClient,
) -> None:
    text = (command.args or "").strip()
    if not text:
        await message.answer("Использование: /broadcast текст сообщения")
        return

    try:
        broadcast_id = await backend.admin_broadcast(text, interface_filter="telegram")
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
        return

    await message.answer(f"Broadcast поставлен в очередь: <code>{broadcast_id}</code>", parse_mode="HTML")
