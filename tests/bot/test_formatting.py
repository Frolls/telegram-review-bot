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
