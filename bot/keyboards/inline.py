from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


TOPICS: dict[str, str] = {
    "code_review": "Код-ревью",
    "python": "Python",
    "ansible": "Ansible",
    "tests": "Тесты",
    "refactoring": "Рефакторинг",
}


def topics_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slug, title in TOPICS.items():
        builder.button(text=title, callback_data=f"topic:{slug}")
    builder.button(text="Отмена", callback_data="topic:cancel")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def feedback_kb(message_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👍", callback_data=f"fb:up:{message_id}")
    builder.button(text="👎", callback_data=f"fb:down:{message_id}")
    builder.adjust(2)
    return builder.as_markup()
