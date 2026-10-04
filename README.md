> Общий README, конфигурация запуска, презентация и отчёт исправлений
> прилагаются автором отдельно при сдаче. Общий запуск — из папки с обоими
> репозиториями и приложенным Compose, по инструкции из общего README.
> API теперь требует внутренний ключ и ID пользователя; примеры ниже без этих
> заголовков относятся к прежним этапам курса.

# Telegram Review Bot

Telegram-интерфейс для дипломного проекта «ИИ-ассистент для ревью кода».

Бот не хранит историю и не содержит LLM-логику. Он ходит в backend chat-сервиса:

- `POST /chats`
- `POST /chats/{chat_id}/messages` со SSE-стримом и `multipart/form-data`
- `POST /chats/{chat_id}/messages/{message_id}/feedback`
- `GET /chats/admin/stats`
- `GET /chats/admin/users`
- `POST /chats/admin/broadcast`
- `DELETE /chats/{chat_id}/messages`
- `POST /notify` — внутренний backchannel для уведомлений от backend

## Запуск

Клонируйте backend в соседний каталог `Review_bot` по инструкции из общего README,
приложенного к защите. Поместите общую конфигурацию в родительскую папку.
Из каталога бота перейдите в неё:

```bash
cd ..
cp .env.example .env
# заполнить BOT_TOKEN, INTERNAL_TOKEN, ADMIN_TOKEN и параметры модели
docker compose up -d --build
```

Для отдельного запуска бота:

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
ADMIN_TOKEN=changeme-admin
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

Проверенный результат от 4 октября 2026: `28 passed`.

## Возможности

- `/start` — создаёт чат в backend и показывает доменное приветствие.
- `/help` — список команд.
- `/clear` — очищает историю текущего backend-чата.
- `/cancel` — сбрасывает FSM-сценарий.
- `/ask` — сценарий выбора темы и отправки вопроса в backend.
- `/stats` — admin-команда: показывает backend-статистику за 24 часа.
- `/users` — admin-команда: показывает последних пользователей.
- `/broadcast <text>` — admin-команда: ставит Telegram broadcast в backend-очередь.
- Reply-кнопки дублируют основные команды: выбор темы, очистка истории, помощь и отмена.
- Backend проверяет ответ модерацией до выдачи. Бот читает SSE и показывает
  полный ответ страницами с сохранением кода и лимита длины Telegram.
- Источники, на которые ссылается ответ, показываются с исходными номерами
  и полным текстом найденного фрагмента. Если ссылок в ответе нет, найденные
  фрагменты отмечаются отдельно. Наличие ссылки не гарантирует правильность вывода модели.
- `/agent` — инструменты, просмотр ожидающего действия и подтверждение либо отмена отправки.
- Фото отправляются в backend как `image/jpeg`.
- Голосовые сообщения и аудиофайлы отправляются как audio multipart.
- Документы PDF/DOCX отправляются в backend как файлы; остальные документы отклоняются ботом.
- После каждого ответа бот добавляет inline-кнопки 👍/👎. Callback отправляет
  в backend `up/down`, id сохранённого сообщения и список фактически показанных
  RAG sources.
- В фоне бот забирает pending broadcast'ы из backend и отправляет их Telegram-пользователям.

Admin-команды доступны только пользователям, чьи Telegram ID перечислены в
`BOT_ADMIN_IDS`. Проверка выполняется фильтром `IsAdmin` на уровне router.

## Замечания

Для корректного доменного поведения backend должен сам задавать system prompt для Telegram-интерфейса или принимать `system_prompt` при создании чата. Бот намеренно не знает про LLM и не хранит историю.

`INTERNAL_TOKEN` должен совпадать с одноимённой переменной backend. Voice-сценарий
зависит от backend: ему нужен OpenAI-compatible endpoint `/audio/transcriptions`;
при работе напрямую с Ollama голосовые сообщения могут быть отклонены.

`ADMIN_TOKEN` должен совпадать с одноимённой переменной backend. Бот не вызывает
OpenAI Moderation API и не реализует собственный rate limit: модерация,
админ-статистика и feedback находятся на стороне backend.
