from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


HELP_BUTTON = "Помощь"
CLEAR_BUTTON = "Очистить историю"
ASK_BUTTON = "Выбрать тему"
CANCEL_BUTTON = "Отмена"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=ASK_BUTTON),
                KeyboardButton(text=CLEAR_BUTTON),
            ],
            [
                KeyboardButton(text=HELP_BUTTON),
                KeyboardButton(text=CANCEL_BUTTON),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправьте код, документ, фото или вопрос",
    )
