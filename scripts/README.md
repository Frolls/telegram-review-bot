# Живая проверка клиента и API бота

Эти скрипты перенесены из общего workspace без изменения содержимого: их хеши
соответствуют исходному протоколу backend. Запускайте из корня репозитория бота
в установленном окружении `pip install -e '.[dev]'`.

`serve_bot_acceptance.py` запускает настоящий `bot.web.build_api` на порту 8081,
без Telegram polling и broadcasts. Он сохраняет только путь, метод, статус и
время обращения; заголовки и тела запросов в аудит не попадают.

При готовом backend задайте `INTERNAL_TOKEN` в окружении. В отдельном терминале,
когда порт 8081 свободен:

```bash
mkdir -p var/verification
BOT_TOKEN=123456:ACCEPTANCE \
  ACCEPTANCE_ACCESS_LOG="$PWD/var/verification/bot-access.jsonl" \
  DELIVERY_DB_PATH="$PWD/var/verification/deliveries.sqlite" \
  PYTHONPATH=. python scripts/serve_bot_acceptance.py
```

Синтетический токен подходит для этого harness, поскольку обращения к Telegram
не выполняются. Не используйте этот процесс как обычный polling-бот.

Во втором терминале из того же репозитория, с тем же `INTERNAL_TOKEN`:

```bash
OWNER_ID=9011032027 PYTHONPATH=. python scripts/live_agent_acceptance.py \
  --backend http://localhost:8000 --bot http://localhost:8081 \
  --output var/verification/agent-live.json
```

Используйте отдельный синтетический `OWNER_ID`: скрипт очищает его чат и checkpoint
агента. Он проверяет readiness, RAG с источником, память, инструменты времени и
поиска, точную цитату, preview/cancel, полную очистку и отклонение старого request ID.
Положительного resume нет. Ошибки сохраняются в том же отчёте; после запуска
проверьте отсутствие `/notify` в аудите. Завершите API harness обычным Ctrl-C.

Контейнерный запуск требует путей, доступных для записи пользователю контейнера,
и адресов backend/bot в его сети. Зафиксированный прогон использовал отдельный
контейнер HTTP API с синтетическим токеном и read-only mounts текущего кода.

Для короткого smoke, измерения ресурсов, native inference и теста пары сервисов
используйте [скрипты backend](https://github.com/Frolls/Review_assistant/blob/main/scripts/README.md).
Сохранённые [результаты](../docs/verification/README.md) не заменяют проверку нового
развёртывания и не доказывают внешнюю доставку Telegram.
