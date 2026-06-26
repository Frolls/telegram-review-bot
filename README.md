# Telegram Review Bot

Telegram-интерфейс для дипломного проекта «ИИ-ассистент для ревью кода».

Бот не хранит историю и не содержит LLM-логику. Он ходит в backend chat-сервиса:

- `POST /chats`
- `POST /chats/{chat_id}/messages` со SSE-стримом
- `DELETE /chats/{chat_id}/messages`

## Запуск

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=...
BACKEND_URL=http://localhost:8000
BOT_ADMIN_IDS=[]
```

Затем запустите backend chat-сервиса и бота:

```bash
python -m bot
```

## Проверка

```bash
pytest tests/bot -v
```

## Возможности

- `/start` — создаёт чат в backend и показывает доменное приветствие.
- `/help` — список команд.
- `/clear` — очищает историю текущего backend-чата.
- `/cancel` — сбрасывает FSM-сценарий.
- `/ask` — сценарий выбора темы и отправки вопроса в backend.
- Обычные текстовые сообщения стримятся из backend и обновляются через `edit_text`.

## Замечания

Для корректного доменного поведения backend должен сам задавать system prompt для Telegram-интерфейса или принимать `system_prompt` при создании чата. Бот намеренно не знает про LLM и не хранит историю.
