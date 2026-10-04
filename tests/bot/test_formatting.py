from __future__ import annotations

from bot.handlers.utils import markdown_to_telegram_html


def test_markdown_to_telegram_html_formats_fenced_code_block() -> None:
    text = """### Пример

```yaml
- name: Включить внешние таски
  include_tasks: path/to/tasks.yml
```
"""

    rendered = markdown_to_telegram_html(text)

    assert "<b>Пример</b>" in rendered
    assert '<pre><code class="language-yaml">' in rendered
    assert "include_tasks: path/to/tasks.yml" in rendered


def test_markdown_to_telegram_html_escapes_code_block_content() -> None:
    rendered = markdown_to_telegram_html("```python\nif a < b:\n    print('ok')\n```")

    assert "a &lt; b" in rendered
    assert "<pre><code" in rendered


def test_markdown_to_telegram_html_repairs_stuck_yaml_fence() -> None:
    rendered = markdown_to_telegram_html(
        "```yaml- name: Подключить роль  import_role:    name: my_role```"
    )

    assert '<pre><code class="language-yaml">' in rendered
    assert "- name: Подключить роль\n  import_role:\n    name: my_role" in rendered


def test_markdown_to_telegram_html_repairs_stuck_text_fence() -> None:
    rendered = markdown_to_telegram_html(
        "```textroles/my_role/  tasks/main.yml  handlers/main.yml```"
    )

    assert '<pre><code class="language-text">' in rendered
    assert "roles/my_role/\n  tasks/main.yml\n  handlers/main.yml" in rendered


def test_split_keeps_code_and_entities_intact_across_pages():
    from html.parser import HTMLParser
    from bot.handlers.utils import split_answer
    class Inspector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.text, self.code, self.languages = [], [], [], []
        def handle_starttag(self, tag, attrs):
            self.stack.append(tag)
            if tag == "code":
                self.languages.append(dict(attrs).get("class"))
        def handle_endtag(self, tag):
            assert self.stack.pop() == tag
        def handle_data(self, data):
            self.text.append(data)
            if "pre" in self.stack:
                self.code.append(data)
    code = '\n'.join(f'    print("<&> 🐍 {i}")' for i in range(150))
    text = f"**Пример**\n```python\n{code}\n```\nКонец"
    pages = split_answer(text, max_units=130)
    code_parts = []
    plain_parts = []
    for page in pages:
        assert markdown_to_telegram_html(page) == str(page)  # no second escaping
        parsed = Inspector()
        parsed.feed(str(page))
        assert parsed.stack == []
        assert "".join(parsed.text) == page.plain_text
        assert len(page.plain_text.encode("utf-16-le")) // 2 <= 130
        assert all(value == "language-python" for value in parsed.languages)
        code_parts.extend(parsed.code)
        plain_parts.extend(parsed.text)
    assert "".join(code_parts) == code
    whole = Inspector()
    whole.feed(markdown_to_telegram_html(text))
    assert "".join(plain_parts) == "".join(whole.text)


def test_single_long_line_of_code_stays_in_balanced_code_blocks():
    from bot.handlers.utils import split_answer
    code = "x<&🐍" * 2000
    pages = split_answer(f"```python\n{code}\n```", max_units=120)
    assert len(pages) > 2
    assert all("<pre><code" in page and "</code></pre>" in page for page in pages)
    assert "".join(page.plain_text for page in pages).strip("\n") == code


def test_valid_yaml_string_is_not_reformatted():
    from bot.handlers.utils import split_answer
    code = 'message: "keep  two: spaces"'
    pages = split_answer(f"```yaml\n{code}\n```", max_units=30)
    assert "".join(p.plain_text for p in pages).strip("\n") == code


def test_unknown_language_is_preserved_without_becoming_code_content():
    from bot.handlers.utils import split_answer
    code = 'const x = "<&>";\n' * 30
    pages = split_answer(f"```javascript\n{code}```", max_units=100)
    assert "".join(p.plain_text for p in pages).strip("\n") == code.strip("\n")
    assert any('class="language-javascript"' in page for page in pages)
