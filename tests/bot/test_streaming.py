from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.handlers import utils


@pytest.mark.asyncio
async def test_render_stream_renders_complete_moderated_answer(monkeypatch) -> None:
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
    assert edits == ["one two three"]


@pytest.mark.asyncio
async def test_long_response_preserves_all_text_and_telegram_limit(monkeypatch):
    pages = []
    async def display(message, text, **kwargs):
        pages.append(text)
    monkeypatch.setattr(utils, "_edit_text", display)
    monkeypatch.setattr(utils, "_send_message", display)
    answer = "Код 🐍\n" * 2200
    async def chunks():
        yield answer
    assert await utils.render_stream(SimpleNamespace(), chunks()) == answer
    assert "".join(pages) == answer
    assert all(len(p.encode("utf-16-le")) // 2 <= 3500 for p in pages)


def test_sources_are_visible_with_identifiers_and_filenames():
    rendered = utils.source_summary([{"id": 2, "file_name": "rules.md", "page": 3, "text": "Do not leak secrets"}])
    assert "[2] rules.md, стр. 3" in rendered
    assert "Do not leak secrets" in rendered


def test_source_numbers_follow_prose_citations_without_treating_code_as_evidence():
    sources = [
        {"id": 1, "file_name": "unrelated.md", "snippet": "Other topic"},
        {"id": 3, "file_name": "defaults.md", "snippet": "Use None"},
    ]
    answer = "Read `items[1]`.\n```python\nvalues = [1]\n```\nUse None [3]."
    rendered = utils.source_summary(sources, answer)
    assert "[3] defaults.md" in rendered
    assert "unrelated.md" not in rendered
    assert "Источники, указанные в ответе:" in rendered


def test_uncited_retrieval_is_labeled_without_claiming_answer_support():
    rendered = utils.source_summary(
        [{"id": 1, "file_name": "defaults.md", "snippet": "Use None"}],
        "The answer omitted its citations.",
    )
    assert "ответ без ссылок на них" in rendered
    assert "[1] defaults.md" in rendered


@pytest.mark.asyncio
async def test_stream_displays_complete_cited_fragment_across_pages(monkeypatch):
    from uuid import uuid4
    from unittest.mock import AsyncMock

    excerpt = "Earlier text. " * 320 + "Mutable defaults are shared; use None."
    class Stream:
        message_id = uuid4()
        sources = [
            {"id": 1, "file_name": "defaults.md", "snippet": excerpt},
            {"id": 2, "file_name": "unrelated.md", "snippet": "Other topic"},
        ]
        def __aiter__(self):
            async def chunks():
                yield "Use None [1]."
            return chunks()

    sent = []
    async def send(message, text, **kwargs):
        sent.append((text, kwargs.get("reply_markup")))
    monkeypatch.setattr(utils, "_edit_text", AsyncMock())
    monkeypatch.setattr(utils, "_send_message", send)
    message = SimpleNamespace(
        chat=SimpleNamespace(id=42),
        bot=SimpleNamespace(send_chat_action=AsyncMock()),
        answer=AsyncMock(return_value=SimpleNamespace()),
    )

    await utils.stream_to_chat(message, Stream())

    text = "".join(page.plain_text for page, _ in sent)
    assert excerpt in text
    assert "[1] defaults.md" in text
    assert "unrelated.md" not in text
    assert len(sent) > 1
    assert all(len(page.plain_text.encode("utf-16-le")) // 2 <= 3500 for page, _ in sent)
    assert all(markup is None for _, markup in sent[:-1])
    assert sent[-1][1] is not None
