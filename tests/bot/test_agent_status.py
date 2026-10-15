from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot.handlers.agent import agent_command


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["pending", "agent", "display"])
async def test_network_failure_leaves_no_running_status(failure_stage):
    status = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(text="/agent time", from_user=SimpleNamespace(id=1001), answer=AsyncMock(return_value=status))
    error = httpx.ReadTimeout("Timeout")
    backend = SimpleNamespace(
        pending_action=AsyncMock(side_effect=error if failure_stage == "pending" else [None, error] if failure_stage == "display" else [None]),
        agent=AsyncMock(side_effect=error if failure_stage == "agent" else None, return_value=[]),
    )
    await agent_command(message, backend)
    if failure_stage == "pending":
        status.edit_text.assert_not_awaited()
        assert "долго отвечает" in message.answer.await_args.args[0]
    else:
        assert "долго отвечает" in status.edit_text.await_args.args[0]
        assert message.answer.await_count == 1


@pytest.mark.asyncio
async def test_agent_http_conflict_replaces_running_status_with_backend_detail():
    status = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(text="/agent time", from_user=SimpleNamespace(id=1001), answer=AsyncMock(return_value=status))
    response = httpx.Response(409, json={"detail": "Этот диалог уже обрабатывается"}, request=httpx.Request("POST", "http://backend/agent/stream"))
    error = httpx.HTTPStatusError("Conflict", request=response.request, response=response)
    backend = SimpleNamespace(pending_action=AsyncMock(return_value=None), agent=AsyncMock(side_effect=error))
    await agent_command(message, backend)
    status.edit_text.assert_awaited_once_with("Этот диалог уже обрабатывается")
    assert message.answer.await_count == 1


def test_error_formatter_handles_an_unread_stream_without_crashing():
    from bot.handlers.utils import backend_error_text

    class UnreadBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"unavailable"

    response = httpx.Response(503, stream=UnreadBody(), request=httpx.Request("POST", "http://backend/agent/stream"))
    error = httpx.HTTPStatusError("Unavailable", request=response.request, response=response)
    assert "503" in backend_error_text(error)


@pytest.mark.asyncio
async def test_agent_passes_user_question_without_adding_recipient_to_prompt():
    from unittest.mock import patch

    status = SimpleNamespace(edit_text=AsyncMock())
    question = "Вызови get_current_time для Asia/Yekaterinburg и сообщи текущее время."
    message = SimpleNamespace(text="/agent " + question, from_user=SimpleNamespace(id=1001), answer=AsyncMock(return_value=status))
    backend = SimpleNamespace(pending_action=AsyncMock(return_value=None), agent=AsyncMock(return_value=[]))
    with patch("bot.handlers.agent.display_events", new_callable=AsyncMock):
        await agent_command(message, backend)
    payload = backend.agent.await_args.args[0]
    assert payload["input"]["messages"] == [{"role": "user", "content": question}]
