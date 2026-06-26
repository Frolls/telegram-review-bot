from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.handlers.fsm import ask_command, choose_topic
from bot.states import AskFlow


@pytest.mark.asyncio
async def test_ask_flow_select_topic_moves_to_waiting_for_question() -> None:
    message = AsyncMock()
    state = AsyncMock()

    await ask_command(message, state)

    state.set_state.assert_awaited_with(AskFlow.waiting_for_topic)
    message.answer.assert_awaited()

    callback = AsyncMock()
    callback.data = "topic:ansible"
    callback.message = AsyncMock()
    state.reset_mock()

    await choose_topic(callback, state)

    state.update_data.assert_awaited_with(topic="Ansible")
    state.set_state.assert_awaited_with(AskFlow.waiting_for_question)
    callback.answer.assert_awaited()
