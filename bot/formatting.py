"""Split rendered Telegram HTML without breaking entities or code blocks."""
from __future__ import annotations

import html
from html.parser import HTMLParser


class TelegramHTML(str):
    """Already rendered HTML with an exact plain-text fallback."""
    plain_text: str

    def __new__(cls, markup: str, plain_text: str):
        instance = super().__new__(cls, markup)
        instance.plain_text = plain_text
        return instance


class _PageParser(HTMLParser):
    def __init__(self, limit: int):
        super().__init__(convert_charrefs=True)
        if limit < 2:
            raise ValueError("Page limit must be at least two UTF-16 units")
        self.limit = limit
        self.stack: list[tuple[str, str]] = []
        self.markup: list[str] = []
        self.plain: list[str] = []
        self.units = 0
        self.pages: list[TelegramHTML] = []

    def handle_starttag(self, tag, attrs):
        opening = self.get_starttag_text()
        self.markup.append(opening)
        self.stack.append((tag, opening))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError("Unbalanced generated Telegram HTML")
        self.markup.append(f"</{tag}>")
        self.stack.pop()

    def handle_data(self, data: str):
        while data:
            remaining = self.limit - self.units
            end = 0
            used = 0
            for character in data:
                width = 2 if ord(character) > 0xFFFF else 1
                if used + width > remaining:
                    break
                used += width
                end += 1
            if end == 0:
                self.flush()
                continue
            # Prefer complete lines. Very long lines still fit safely inside
            # independently reopened <pre><code> blocks on subsequent pages.
            if end < len(data):
                line_end = data.rfind("\n", 0, end) + 1
                if line_end:
                    end = line_end
            piece, data = data[:end], data[end:]
            self.markup.append(html.escape(piece, quote=False))
            self.plain.append(piece)
            self.units += len(piece.encode("utf-16-le")) // 2
            if data:
                self.flush()

    def flush(self):
        if not self.plain:
            return
        closing = "".join(f"</{tag}>" for tag, _ in reversed(self.stack))
        self.pages.append(TelegramHTML("".join(self.markup) + closing, "".join(self.plain)))
        self.markup = [opening for _, opening in self.stack]
        self.plain = []
        self.units = 0


def paginate_html(markup: str, max_units: int = 3500) -> list[TelegramHTML]:
    parser = _PageParser(max_units)
    parser.feed(markup)
    parser.close()
    if parser.stack:
        raise ValueError("Unclosed generated Telegram HTML")
    parser.flush()
    return parser.pages
