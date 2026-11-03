# Запуск полного стенда

Compose обоих сервисов и общий шаблон `.env` версионируются в backend:
[инструкция развёртывания](https://github.com/Frolls/Review_assistant/blob/main/DEPLOYMENT.md),
[deploy/compose.yaml](https://github.com/Frolls/Review_assistant/blob/main/deploy/compose.yaml).
Отдельные файлы из папки Diploma не нужны.

В общей рабочей папке:

```bash
git clone https://github.com/Frolls/Review_assistant.git Review_bot
git clone https://github.com/Frolls/telegram-review-bot.git telegram-review-bot
if [ ! -e .env ]; then cp Review_bot/deploy/.env.example .env; fi
```

Заполните `.env` своим `BOT_TOKEN` и общими с backend `INTERNAL_TOKEN` / `ADMIN_TOKEN`.
Настройте доступную из контейнеров Ollama и модели по инструкции backend.
Существующий `.env` не перезаписывайте; новые параметры сверяйте с шаблоном.

Из той же общей папки:

```bash
docker compose --project-directory "$PWD" --env-file .env \
  -f Review_bot/deploy/compose.yaml up -d --build
curl --fail http://localhost:8000/ready
```

Бот начинает polling после готовности backend. Не запускайте второй процесс
polling с тем же токеном. Backend вызывает HTTP API бота внутри сети по
`http://bot:8081`; `POST /notify` требует внутренний ключ и request ID.
Журнал доставки хранится в постоянном volume. `down -v` удаляет постоянные данные.

Проверка обоих репозиториев:

```bash
sh Review_bot/scripts/test_all.sh
```

Для отдельного запуска бота используйте [README](README.md). Проверка девяти
ходов агента без polling и положительного подтверждения описана в
[scripts/README.md](scripts/README.md); сохранённые результаты — в
[docs/verification](docs/verification/README.md).
