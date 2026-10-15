# Telegram Review Bot

Telegram-интерфейс дипломного проекта — ассистента для разработки
и ревью Python и Ansible. Работает в **личных чатах**: передаёт вопросы и вложения
в [backend](https://github.com/Frolls/Review_assistant), показывает ответы,
источники и кнопки подтверждения действий агента.

LLM, поиск и история диалога находятся в backend. Бот хранит собственный
SQLite-журнал доставки уведомлений; состояние сценария `/ask` находится в памяти
процесса и сбрасывается при перезапуске.

## Запуск полного стенда

Для защиты используются **два репозитория и общий комплект файлов запуска**,
который автор прилагает отдельно: `compose.yaml`, `.env.example`, общий README,
`docs/` и `scripts/`. Поместите их в одну рабочую папку, например `Diploma/`,
и из неё выполните:

```bash
git clone https://github.com/Frolls/Review_assistant.git Review_bot
git clone https://github.com/Frolls/telegram-review-bot.git telegram-review-bot
if [ ! -e .env ]; then cp .env.example .env; fi
```

Структура запуска:

```text
Diploma/
├── compose.yaml           # общий файл из комплекта защиты
├── .env.example
├── .env
├── README.md
├── docs/
├── scripts/
├── Review_bot/
└── telegram-review-bot/   # этот репозиторий
```

Нужны Docker с Compose и отдельно запущенная Ollama, доступная из контейнеров
по `host.docker.internal:11434`, с моделями `qwen3:8b` и `qwen3-embedding:4b`.
В общем `.env` заполните `BOT_TOKEN`, замените `INTERNAL_TOKEN` и `ADMIN_TOKEN`.
Общий Compose передаёт одинаковые внутренние ключи backend и боту.

Из общей папки:

```bash
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml ps
curl --fail http://localhost:8000/ready
```

Compose поднимает бот, API, PostgreSQL, Redis, Qdrant и Phoenix. Бот ждёт готовности
API, включая первоначальную индексацию. После запуска отправьте боту `/start`.
Логи: `docker compose -f compose.yaml logs --tail=100 bot app`.

Используйте именно **общий** `Diploma/compose.yaml`. Вложенный
`Review_bot/compose.yaml` — отдельная конфигурация разработки с другими `.env`
и настройками хранения. Обе конфигурации одновременно запускать не следует.

## Отдельный запуск бота для разработки

Нужны Python **3.11–3.13** и уже работающий backend. Команды ниже выполняются
из каталога `telegram-review-bot/`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
if [ ! -e .env ]; then cp .env.example .env; fi
```

Настройте локальный `.env`:

```dotenv
BOT_TOKEN=REPLACE_WITH_TELEGRAM_BOT_TOKEN
BACKEND_URL=http://localhost:8000
BOT_API_PORT=8081
INTERNAL_TOKEN=REPLACE_WITH_BACKEND_INTERNAL_TOKEN
ADMIN_TOKEN=REPLACE_WITH_BACKEND_ADMIN_TOKEN
BOT_ADMIN_IDS=[]
```

`BOT_ADMIN_IDS` — список числовых Telegram ID, например `[123456789]`.
`INTERNAL_TOKEN` и `ADMIN_TOKEN` должны совпадать с backend.
Для запуска задайте доступный для записи путь журнала доставки:

```bash
mkdir -p var
export DELIVERY_DB_PATH="$PWD/var/deliveries.sqlite"
python -m bot
```

`DELIVERY_DB_PATH` читается напрямую из окружения процесса: одной записи
этой переменной в `.env` при запуске `python -m bot` недостаточно.
В контейнерном запуске общий Compose сам задаёт `/app/var/deliveries.sqlite`
и подключает постоянный volume.

Для уведомлений backend должен обращаться к API этого экземпляра бота:
`BOT_URL=http://localhost:8081`, если оба процесса на хосте, либо
`http://host.docker.internal:8081`, если backend в контейнере и этот адрес доступен
из его сети. При таком варианте переопределите `BOT_URL` backend: общий Compose
по умолчанию направляет его на контейнер `bot`.
Не запускайте два процесса polling с одним `BOT_TOKEN`; перед отдельным запуском
остановите контейнер бота командой `docker compose -f compose.yaml stop bot`
из общей папки.

## Команды и вложения

| Команда | Действие |
| --- | --- |
| `/start` | Создать или открыть диалог и показать приветствие |
| `/help` | Показать команды |
| `/ask` | Выбрать тему и задать вопрос |
| `/clear` | Очистить историю текущего диалога в backend |
| `/cancel` | Сбросить сценарий выбора темы `/ask` |
| `/agent <запрос>` | Вызвать агента с инструментами |
| `/agent` | Показать ожидающее подтверждения действие |
| `/stats`, `/users` | Статистика и пользователи; только администраторы |
| `/broadcast <текст>` | Поставить рассылку в очередь backend; только администраторы |

Действие агента отменяется **его inline-кнопкой**, а не командой `/cancel`.
Перед отправкой сообщения агент показывает действие и ожидает подтверждения.
Отправка ограничена собственным Telegram-чатом пользователя.

Обычный вопрос можно отправить без команды. Бот получает ответ по SSE и показывает
его страницами с сохранением кода. Под ответом доступны источники и 👍/👎.
При обратной связи в backend передаются ID сообщения и фактически показанные
источники. Ссылка на источник сама по себе не гарантирует правильность вывода.

Принимаются документы до **10 МиБ** с расширениями:
`.pdf`, `.docx`, `.py`, `.yaml`, `.yml`, `.diff`, `.patch`, `.txt`, `.md`, `.json`, `.toml`.
Файл передаётся в личный диалог для анализа; его содержимое не добавляется
в общую базу знаний. Общая база пополняется через административный API backend.

Фото отправляются как JPEG; поддержка анализа зависит от vision-модели backend.
Голосовые сообщения и аудио требуют совместимого `/audio/transcriptions`.
Наличие обработчика в боте не означает, что эти возможности доступны у выбранной
модели Ollama.

Административные команды проверяют Telegram ID по `BOT_ADMIN_IDS`, а запросы
административного API — общий `ADMIN_TOKEN`. Модерация и лимиты запросов реализованы
на стороне backend.

## Взаимодействие с backend

Бот передаёт `X-Internal-Token` и `X-User-ID`, полученный из Telegram update.
Пользователь не задаёт идентификатор текстом сообщения. Основные вызовы:

| API backend | Назначение |
| --- | --- |
| `POST /chats` | Получить или создать чат пользователя |
| `POST /chats/{chat_id}/messages` | Передать текст и необязательное вложение, получить SSE |
| `DELETE /chats/{chat_id}/messages` | Очистить историю |
| `POST /chats/{chat_id}/messages/{message_id}/feedback` | Сохранить оценку |
| `POST /agent/stream`, `GET /agent/pending` | Запустить агента, показать и продолжить ожидающее действие |
| `/chats/admin/*` | Статистика, пользователи, очередь рассылки |

### Внутренний API самого бота

**`POST /notify` находится в боте**, по умолчанию на порту `8081`.
Backend вызывает его с заголовком `X-Internal-Token` и JSON-полями
`chat_id`, `text`, `request_id` после подтверждения действия.
В общем Compose этот порт доступен внутри сети контейнеров.

SQLite-журнал связывает `request_id` с содержимым сообщения. Повтор уже
подтверждённой доставки не отправляет сообщение снова; другое содержимое с тем же
ID или неопределённый результат предыдущей доставки возвращает `409`.
Журнал сохраняется между перезапусками при использовании постоянного volume.
Это состояние доставки, отдельное от истории диалогов в PostgreSQL backend.

## Проверка

В активированном окружении разработки из каталога бота:

```bash
pytest tests/bot -v
```

Из общей папки стенда тесты обоих сервисов запускаются так:

```bash
./scripts/test_all.sh
```

Зафиксированный результат **4 октября 2026 года**: 28 тестов бота пройдены.
Тесты находятся в [tests/bot](tests/bot), реализация клиента —
в [backend_client.py](bot/services/backend_client.py), API уведомлений —
в [web.py](bot/web.py).
