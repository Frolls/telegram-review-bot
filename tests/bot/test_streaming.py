from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.handlers import utils


@pytest.mark.asyncio
async def test_render_stream_debounces_fast_chunks(monkeypatch) -> None:
    edits: list[str] = []
    target = SimpleNamespace(chat=SimpleNamespace(id=42))

    async def chunks():
        for value in ("one", " two", " three"):
            yield value

    async def fake_edit_text(message, text, *, reply_markup=None) -> None:
        assert message is target
        assert reply_markup is None
        edits.append(text)

    utils.LAST_EDIT_AT.clear()
    monkeypatch.setattr(utils, "_edit_text", fake_edit_text)

    result = await utils.render_stream(
        target,
        chunks(),
        min_edit_interval=0.7,
    )

    assert result == "one two three"
    assert edits == ["one", "one two three"]
