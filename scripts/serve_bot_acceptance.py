"""Run the production bot HTTP API without polling or outgoing broadcasts.

This harness uses the real Bot/API, never substitutes endpoints or models.
Use a synthetic BOT_TOKEN and cancel every preview. Access audit contains no
headers or bodies, and confirms that /notify was never requested.
"""
import json
import os
from pathlib import Path
import time

from aiogram import Bot
import uvicorn

from bot.web import build_api

bot = Bot(token=os.environ["BOT_TOKEN"])
api = build_api(bot, os.environ["INTERNAL_TOKEN"])


@api.middleware("http")
async def audit(request, call_next):
    response = await call_next(request)
    with Path(os.environ["ACCEPTANCE_ACCESS_LOG"]).open("a") as output:
        output.write(json.dumps({"time": time.time(), "path": request.url.path,
                                 "method": request.method, "status": response.status_code}) + "\n")
    return response


if __name__ == "__main__":
    uvicorn.run(api, host="0.0.0.0", port=8081)
