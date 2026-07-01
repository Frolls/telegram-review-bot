# Telegram Review Bot

Telegram-интерфейс для дипломного проекта «ИИ-ассистент для ревью кода».

Бот не хранит историю и не содержит LLM-логику. Он ходит в backend chat-сервиса:

- `POST /chats`
- `POST /chats/{chat_id}/messages` со SSE-стримом и `multipart/form-data`
- `DELETE /chats/{chat_id}/messages`
- `POST /notify` — внутренний backchannel для уведомлений от backend

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
BOT_API_PORT=8081
INTERNAL_TOKEN=changeme
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
- Reply-кнопки дублируют основные команды: выбор темы, очистка истории, помощь и отмена.
- Обычные текстовые сообщения стримятся из backend через draft-обновления и финальное сообщение.
- Фото отправляются в backend как `image/jpeg`.
- Голосовые сообщения и аудиофайлы отправляются как audio multipart.
- Документы PDF/DOCX отправляются в backend как файлы; остальные документы отклоняются ботом.

## Замечания

Для корректного доменного поведения backend должен сам задавать system prompt для Telegram-интерфейса или принимать `system_prompt` при создании чата. Бот намеренно не знает про LLM и не хранит историю.

`INTERNAL_TOKEN` должен совпадать с одноимённой переменной backend. Voice-сценарий
зависит от backend: ему нужен OpenAI-compatible endpoint `/audio/transcriptions`;
при работе напрямую с Ollama голосовые сообщения могут быть отклонены.
