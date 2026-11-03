"""Live two-service smoke and multi-turn agent, using the production bot client.

No positive resume and no /notify request. All observations, including failed
assertions, are saved. Use a dedicated synthetic OWNER_ID.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

import httpx

from bot.services.backend_client import BackendClient


async def run(args):
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": [],
              "real_services": True, "real_model": True, "telegram_polling": False,
              "positive_resume": False}
    path = Path(args.output)

    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    owner = os.environ["OWNER_ID"]
    client = BackendClient(args.backend, internal_token=os.environ["INTERNAL_TOKEN"],
                           owner_id=owner, timeout=200)
    headers = client._headers()
    thread = "telegram-actions"

    async def request(method, url, **kwargs):
        async with httpx.AsyncClient(timeout=200) as http:
            response = await http.request(method, args.backend + url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    async def turn(name, question=None, **operation):
        started = time.monotonic()
        step = {"name": name, "question": question, "progress": [], "started_at": datetime.now(timezone.utc).isoformat()}
        report["steps"].append(step)
        async def progress(event):
            step["progress"].append({"seconds": time.monotonic() - started, "event": event})
        payload = {"thread_id": thread, **operation}
        if question is not None:
            payload["input"] = {"messages": [{"role": "user", "content": question}]}
        try:
            step["events"] = await client.agent(payload, on_progress=progress)
            step["seconds"] = time.monotonic() - started
            assert not any(e["event"] == "error" for e in step["events"]), name
            step["transport_passed"] = True
        finally:
            save()
        return step

    def updates(step):
        return [update for event in step["events"] if event["event"] == "updates"
                for update in event["data"].values() if isinstance(update, dict)]

    def tools(step, name):
        return [r for update in updates(step) for r in update.get("tool_results", []) if r["name"] == name]

    def final_text(step):
        messages = [m for update in updates(step) for m in update.get("messages", [])
                    if isinstance(m, dict) and m.get("type") == "ai" and not m.get("tool_calls")]
        return str(messages[-1].get("content", "")) if messages else ""

    try:
        report["backend_ready"] = await request("GET", "/ready")
        assert report["backend_ready"]["status"] == "ok"
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.get(args.bot + "/health")
            response.raise_for_status()
            report["bot_health"] = response.json()
        assert report["bot_health"]["status"] == "ok"
        report["cited_rag"] = await request("POST", "/rag/query", json={"question": "Почему изменяемый аргумент по умолчанию Python разделяется между вызовами?"})
        answer = report["cited_rag"]
        assert answer["confident"] and answer["sources"] and any(f"[{s['id']}]" in answer["answer"] for s in answer["sources"])
        save()
        await client.clear_agent_history()
        await turn("remember_review_label", "Метка текущего ревью кода: CEDAR-731. Запомни её для следующих вопросов в этом диалоге. Подтверди кратко.")
        first = await turn("clock_local", "Вызови get_current_time для Asia/Yekaterinburg и сообщи результат.")
        local = tools(first, "get_current_time")
        assert local and "+05:00" in local[-1]["result"]
        first["check"] = "fresh local tool result with +05:00"
        second = await turn("clock_followup", "Вызови get_current_time ещё раз, теперь для UTC. Используй новый результат, а не прошлое время.")
        utc = tools(second, "get_current_time")
        assert utc and "+00:00" in utc[-1]["result"]
        assert datetime.fromisoformat(utc[-1]["result"]) >= datetime.fromisoformat(local[-1]["result"])
        second["check"] = "new UTC tool result on the same persistent thread"
        knowledge = await turn("knowledge_followup", "Вызови search_knowledge_base с запросом: Python mutable default аргумент None независимые вызовы. Объясни найденное правило.")
        matches = tools(knowledge, "search_knowledge_base")
        assert matches and json.loads(matches[-1]["result"])["sources"]
        source = json.loads(matches[-1]["result"])["sources"][0]
        evidence = source.get("text") or source["snippet"]
        assert final_text(knowledge) == f"Найденное правило [{source['id']}]:\n{evidence}\n\nИсточник: {source['file_name']}"
        knowledge["check"] = "answer quotes actual corpus evidence exactly, with attribution and no invented additions"
        recall = await turn("recall_after_tools", "Какая метка текущего ревью была задана в начале этого диалога? Назови только метку.")
        assert "CEDAR-731" in final_text(recall)
        recall["check"] = "memory preserved across time and knowledge tool turns"
        text = "Приёмка: проверено, отправлять не нужно."
        preview = await turn("preview", f"Подготовь отправку в Telegram чат {owner} точного текста: {text}")
        pending = await client.pending_action()
        preview["pending"] = pending
        assert pending and str(pending["chat_id"]) == owner and pending["text"] == text
        assert any(e["event"] == "paused" for e in preview["events"])
        cancel = await turn("cancel", resume=False, request_id=pending["request_id"])
        assert any(e["event"] == "done" for e in cancel["events"]) and await client.pending_action() is None
        cancel["check"] = "cancel completed, no pending action"
        again = await turn("preview_before_clear", f"Подготовь отправку в Telegram чат {owner} точного текста: Проверка очистки.")
        pending2 = await client.pending_action()
        again["pending"] = pending2
        assert pending2 and pending2["request_id"] != pending["request_id"]
        chat_id = await client.get_or_create_chat(owner, "acceptance")
        await client.clear_all_history(chat_id)
        assert await client.pending_action() is None
        try:
            await client.agent({"thread_id": thread, "resume": False, "request_id": pending2["request_id"]})
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 409
            report["clear_invalidates_old_request"] = True
        else:
            raise AssertionError("Old request accepted after clear")
        forgotten = await turn("memory_after_clear", "Какая метка текущего ревью была задана ранее? Если метка неизвестна, так и скажи.")
        assert "CEDAR-731" not in final_text(forgotten)
        forgotten["check"] = "cleared memory does not retain prior label"
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        try:
            await client.clear_agent_history()
            report["cleanup"] = "agent cleared"
        finally:
            await client.aclose()
            save()
    print(json.dumps({"status": report["status"], "steps": len(report["steps"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://app:8000")
    parser.add_argument("--bot", default="http://bot:8081")
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
