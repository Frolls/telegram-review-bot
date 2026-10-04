from __future__ import annotations

import asyncio
import html
import re
import time
from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

import httpx
from aiogram import Bot
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods.base import TelegramMethod
from aiogram.types import InlineKeyboardMarkup, Message

from bot.keyboards.inline import feedback_kb
from bot.formatting import TelegramHTML, paginate_html


INTERFACE = "telegram"
MIN_EDIT_INTERVAL = 0.7
LAST_EDIT_AT: dict[int, float] = {}
SHOWN_SOURCES: dict[str, list[dict]] = {}


class BackendProtocol(Protocol):
    async def get_or_create_chat(self, owner_external_id: str, interface: str) -> UUID:
        ...

    def send_message(
        self,
        chat_id: UUID,
        content: str,
        media: bytes | None = None,
        mime: str | None = None,
    ) -> AsyncIterator[str]:
        ...


class SendMessageDraft(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "sendMessageDraft"

    chat_id: int
    text: str
    draft_id: int


def owner_external_id(message: Message) -> str:
    if message.from_user is not None:
        return str(message.from_user.id)
    return str(message.chat.id)


async def get_chat_id(message: Message, backend: BackendProtocol) -> UUID:
    return await backend.get_or_create_chat(owner_external_id(message), INTERFACE)


def backend_error_text(error: Exception) -> str:
    if isinstance(error, httpx.ConnectError):
        return "Не могу подключиться к backend. Проверьте, что chat-сервис запущен."
    if isinstance(error, httpx.ReadTimeout):
        return "Backend слишком долго отвечает. Попробуйте ещё раз чуть позже."
    if isinstance(error, httpx.HTTPStatusError):
        try:
            payload = error.response.json()
        except ValueError:
            payload = {}
        error_payload = payload.get("error", {}) if isinstance(payload, dict) else {}
        detail_payload = payload.get("detail", {}) if isinstance(payload, dict) else {}
        code = None
        if isinstance(detail_payload, dict):
            code = detail_payload.get("code")
        if code is None and isinstance(error_payload, dict):
            code = error_payload.get("code")
        if code == "moderation_blocked":
            return "Не могу обработать это сообщение: оно не прошло модерацию."
        detail = error_payload.get("message") if isinstance(error_payload, dict) else None
        if detail is None and isinstance(detail_payload, dict):
            detail = detail_payload.get("message")
        if detail:
            return str(detail)
        return f"Backend вернул ошибку {error.response.status_code}. Попробуйте позже."
    return "Backend временно недоступен. Попробуйте позже."


async def render_stream(
    target: Message,
    chunks: AsyncIterator[str],
    *,
    min_edit_interval: float = MIN_EDIT_INTERVAL,
) -> str:
    # The backend releases text only after moderation. Render complete, bounded
    # pages to avoid Telegram's 4096 UTF-16-unit limit, including astral emoji.
    buffer = "".join([chunk async for chunk in chunks])
    pages = split_answer(buffer)
    if pages:
        await _edit_text(target, pages[0])
        for page in pages[1:]:
            await _send_message(target, page)
    return buffer


def split_answer(text: str, max_units: int = 3500) -> list[TelegramHTML]:
    return paginate_html(markdown_to_telegram_html(text), max_units)


def source_summary(sources: list[dict], answer: str | None = None) -> str:
    numbered = [(index, source) for index, source in enumerate(sources, 1)]
    heading = "Найденные источники:"
    if answer is not None:
        prose = re.sub(r"```.*?```|`[^`]*`", "", answer, flags=re.DOTALL)
        cited_ids = set(re.findall(r"(?<![\w])\[(\d+)\]", prose))
        cited = [(index, source) for index, source in numbered
                 if str(source.get("id", index)) in cited_ids]
        if cited:
            numbered = cited
            heading = "Источники, указанные в ответе:"
        else:
            heading = "Найденные фрагменты (ответ без ссылок на них):"
    lines = [heading]
    for index, source in numbered:
        filename = str(source.get("file_name") or source.get("filename") or source.get("source") or "Документ")[:180]
        page = source.get("page")
        lines.append(f"[{source.get('id', index)}] {filename}" + (f", стр. {page}" if page is not None else ""))
        excerpt = source.get("text") or source.get("snippet")
        if excerpt:
            lines.append(str(excerpt).strip())
        lines.append("")
    return "\n".join(lines)


async def stream_to_chat(message: Message, chunks: AsyncIterator[str]) -> str:
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    target = await message.answer("⏳ Готовлю ответ…")
    try:
        buffer = await render_stream(target, chunks, min_edit_interval=MIN_EDIT_INTERVAL)
    except (httpx.HTTPError, RuntimeError) as exc:
        await _edit_text(target, str(exc) if isinstance(exc, RuntimeError) else backend_error_text(exc))
        return ""
    if not buffer:
        await _edit_text(target, "Backend не вернул текст ответа. Попробуйте ещё раз.")
        return ""
    message_id = getattr(chunks, "message_id", None)
    sources = getattr(chunks, "sources", [])
    markup = feedback_kb(str(message_id)) if message_id is not None else None
    if sources:
        pages = split_answer(source_summary(sources, answer=buffer))
        for index, page in enumerate(pages):
            await _send_message(message, page, reply_markup=markup if index == len(pages) - 1 else None)
    elif markup:
        await _send_message(message, "Оцените ответ", reply_markup=markup)
    return buffer


async def _send_message_draft(bot: Bot, chat_id: int, text: str, draft_id: int) -> None:
    try:
        native = getattr(bot, "send_message_draft", None)
        if native is not None:
            await native(chat_id=chat_id, text=text, draft_id=draft_id)
            return
        await bot(SendMessageDraft(chat_id=chat_id, text=text, draft_id=draft_id))
    except TelegramRetryAfter:
        return


async def _send_message(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    rendered_text = markdown_to_telegram_html(text)
    while True:
        try:
            return await message.bot.send_message(
                chat_id=message.chat.id,
                text=rendered_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except TelegramRetryAfter as error:
            await asyncio.sleep(float(error.retry_after) + 0.1)
        except TelegramBadRequest as error:
            if _should_fallback_to_plain_text(error):
                return await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=getattr(text, "plain_text", text),
                    reply_markup=reply_markup,
                )
            raise


def _normalize_assistant_text(text: str) -> str:
    text = re.sub(r"(?<=[А-Яа-яЁё])(?=[A-Za-z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=[А-Яа-яЁё])", " ", text)
    text = re.sub(r"\bревьюю\b", "ревью", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _edit_text(
    target: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    rendered_text = markdown_to_telegram_html(text)
    while True:
        try:
            await target.edit_text(
                rendered_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            return
        except TelegramRetryAfter as error:
            await asyncio.sleep(float(error.retry_after) + 0.1)
        except TelegramBadRequest as error:
            if "message is not modified" in error.message.lower():
                return
            if _should_fallback_to_plain_text(error):
                await target.edit_text(getattr(text, "plain_text", text), reply_markup=reply_markup)
                return
            raise


def _should_fallback_to_plain_text(error: TelegramBadRequest) -> bool:
    message = error.message.lower()
    return (
        "can't parse entities" in message
        or "unsupported start tag" in message
        or "entity" in message
    )


def markdown_to_telegram_html(text: str) -> str:
    if isinstance(text, TelegramHTML):
        return str(text)
    parts: list[str] = []
    cursor = 0

    for match in re.finditer(r"```([^\n`]*)\n?(.*?)```", text, flags=re.DOTALL):
        parts.append(_format_markdown_inline(text[cursor : match.start()]))
        language, code_text = _parse_fence(match.group(1), match.group(2))
        # A valid fenced block is source code: never infer line breaks inside
        # its string literals. Repair applies only to malformed stuck fences.
        code_text = (code_text.strip("\n") if match.group(1).strip() == language
                     else _normalize_code_block(language, code_text))
        code = html.escape(code_text)
        class_attr = f' class="language-{html.escape(language)}"' if language else ""
        parts.append(f"\n<pre><code{class_attr}>{code}</code></pre>\n")
        cursor = match.end()

    parts.append(_format_markdown_inline(text[cursor:]))
    return "".join(parts)


def _format_markdown_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?m)^#{1,6}\s+(.+)$", r"<b>\1</b>", escaped)
    return escaped


def _parse_fence(raw_info: str, raw_code: str) -> tuple[str, str]:
    info = raw_info.strip()
    if raw_code and re.fullmatch(r"[A-Za-z0-9_+#.+-]{1,64}", info):
        return info, raw_code
    known_languages = ("yaml", "yml", "bash", "sh", "python", "py", "json", "text")
    if info in known_languages:
        return info, raw_code

    for language in known_languages:
        if info.startswith(language):
            code_prefix = info[len(language) :].lstrip()
            code = code_prefix
            if code and raw_code:
                code += "\n"
            code += raw_code
            return language, code

    return "", f"{raw_info}\n{raw_code}" if raw_code else raw_info


def _normalize_code_block(language: str, code: str) -> str:
    code = code.strip("\n")
    if "\n" in code:
        return code

    if language in {"yaml", "yml"}:
        return re.sub(
            r" {2,}(?=(?:-\s+|[A-Za-z_][\w-]*:|#))",
            lambda match: "\n" + match.group(0),
            code,
        ).lstrip("\n")

    if language == "text":
        return re.sub(
            r" {2,}(?=[A-Za-z0-9_./-])",
            lambda match: "\n" + match.group(0),
            code,
        ).lstrip("\n")

    return code
