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
