# Changelog

## [2026-07-01]

### Added

- Added media handlers for Telegram photos, voice messages, audio files, and PDF/DOCX documents.
- Added multipart forwarding to the backend `POST /chats/{chat_id}/messages` endpoint.
- Added Bot API draft streaming with a final formatted Telegram message.
- Added a reply keyboard for common actions: topic selection, history clearing, help, and cancel.
- Added internal FastAPI `/notify` endpoint protected by `X-Internal-Token`.
- Added `BOT_API_PORT` and `INTERNAL_TOKEN` configuration.

### Changed

- Changed text and FSM flows to use the shared streaming helper.
- Removed the extra "Сценарий завершён." message after FSM answers.
- Improved backend SSE parsing for JSON `token`, `done`, and `error` events.

### Verified

- Verified bot tests: `10 passed`.
- Verified whitespace sanity with `git diff --check`.
