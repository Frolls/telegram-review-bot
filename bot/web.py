from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3

from aiogram import Bot
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


class NotifyRequest(BaseModel):
    chat_id: int
    text: str = Field(min_length=1, max_length=4000)
    request_id: str = Field(min_length=1, max_length=128)


def build_api(bot: Bot, internal_token: str, *, delivery_db: str | None = None) -> FastAPI:
    api = FastAPI()
    db_path = delivery_db or os.getenv("DELIVERY_DB_PATH", "/app/var/deliveries.sqlite")

    @api.post("/notify")
    async def notify(req: NotifyRequest, x_internal_token: str = Header(...)) -> dict[str, bool]:
        if not secrets.compare_digest(x_internal_token, internal_token):
            raise HTTPException(status_code=401)
        if len(req.text.encode("utf-16-le")) // 2 > 4000:
            raise HTTPException(status_code=422, detail="Сообщение слишком длинное")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(json.dumps([req.chat_id, req.text]).encode()).hexdigest()
        # Commit reservation before the network call. An uncertain delivery is
        # never retried automatically: Telegram provides no idempotency key.
        with sqlite3.connect(db_path, timeout=5) as db:
            db.execute("CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, digest TEXT NOT NULL, state TEXT NOT NULL)")
            inserted = db.execute("INSERT OR IGNORE INTO deliveries VALUES (?, ?, 'pending')", (req.request_id, digest)).rowcount
            row = db.execute("SELECT digest, state FROM deliveries WHERE id=?", (req.request_id,)).fetchone()
        if row[0] != digest:
            raise HTTPException(status_code=409, detail="Request ID reused with another payload")
        if not inserted:
            if row[1] == "sent":
                return {"ok": True, "duplicate": True}
            raise HTTPException(status_code=409, detail="Статус доставки неизвестен. Проверьте чат; автоматический повтор запрещён.")
        try:
            await bot.send_message(chat_id=req.chat_id, text=req.text)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Доставка не подтверждена. Проверьте чат перед новой отправкой.") from exc
        with sqlite3.connect(db_path, timeout=5) as db:
            db.execute("UPDATE deliveries SET state='sent' WHERE id=?", (req.request_id,))
        return {"ok": True, "duplicate": False}

    return api
