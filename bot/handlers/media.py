from __future__ import annotations

from io import BytesIO

import httpx
from aiogram import F, Router
from aiogram.types import Audio, Document, Message, PhotoSize, Voice

from bot.handlers.utils import backend_error_text, get_chat_id, stream_to_chat
from bot.services.backend_client import BackendClient


router = Router()

MAX_PHOTO_SIZE = 2 * 1024 * 1024
PREFERRED_PHOTO_SIZE = 768 * 1024
PREFERRED_PHOTO_MAX_SIDE = 768
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
SUPPORTED_DOCUMENT_EXTENSIONS = (".pdf", ".docx")


@router.message(F.photo)
async def photo_message(message: Message, backend: BackendClient) -> None:
    photo = _select_photo(message.photo or [])
    if photo is None:
        await message.answer("Фото слишком большое. Отправьте изображение до 2 МБ.")
        return

    await _send_media_message(
        message,
        backend,
        content=message.caption or "[фото]",
        media=await _download_file(message, photo.file_id),
        mime="image/jpeg",
    )


@router.message(F.voice)
async def voice_message(message: Message, backend: BackendClient) -> None:
    voice: Voice = message.voice
    await _send_media_message(
        message,
        backend,
        content=message.caption or "[голосовое сообщение]",
        media=await _download_file(message, voice.file_id),
        mime="audio/ogg",
    )


@router.message(F.audio)
async def audio_message(message: Message, backend: BackendClient) -> None:
    audio: Audio = message.audio
    await _send_media_message(
        message,
        backend,
        content=message.caption or audio.file_name or "[аудио]",
        media=await _download_file(message, audio.file_id),
        mime=audio.mime_type or "audio/mpeg",
    )


@router.message(F.document)
async def document_message(message: Message, backend: BackendClient) -> None:
    document: Document = message.document
    filename = (document.file_name or "").lower()
    if not filename.endswith(SUPPORTED_DOCUMENT_EXTENSIONS):
        await message.answer("Поддерживаются только PDF и DOCX.")
        return
    if document.file_size and document.file_size > MAX_DOCUMENT_SIZE:
        await message.answer("Документ слишком большой. Отправьте файл до 10 МБ.")
        return

    mime = document.mime_type
    if filename.endswith(".pdf"):
        mime = mime or "application/pdf"
    elif filename.endswith(".docx"):
        mime = mime or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    await _send_media_message(
        message,
        backend,
        content=message.caption or document.file_name or "[документ]",
        media=await _download_file(message, document.file_id),
        mime=mime,
    )


def _select_photo(sizes: list[PhotoSize]) -> PhotoSize | None:
    eligible = [
        size
        for size in sizes
        if size.file_size is None or size.file_size <= MAX_PHOTO_SIZE
    ]
    if not eligible:
        return None
    preferred = [
        size
        for size in eligible
        if (
            (size.file_size is None or size.file_size <= PREFERRED_PHOTO_SIZE)
            and max(size.width, size.height) <= PREFERRED_PHOTO_MAX_SIDE
        )
    ]
    if preferred:
        return max(preferred, key=lambda size: (size.width * size.height, size.file_size or 0))
    return min(eligible, key=lambda size: (size.width * size.height, size.file_size or 0))


async def _download_file(message: Message, file_id: str) -> bytes:
    file = await message.bot.get_file(file_id)
    buffer = BytesIO()
    await message.bot.download_file(file.file_path, destination=buffer)
    return buffer.getvalue()


async def _send_media_message(
    message: Message,
    backend: BackendClient,
    *,
    content: str,
    media: bytes,
    mime: str | None,
) -> None:
    try:
        chat_id = await get_chat_id(message, backend)
        await stream_to_chat(
            message,
            backend.send_message(chat_id, content, media=media, mime=mime),
        )
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        await message.answer(backend_error_text(error))
