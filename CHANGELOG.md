# Changelog

## [2026-07-27]

### Added

- Added parsing of final backend SSE metadata: `message_id`, `sources`, and `confident`.
- Added forwarding of the sources shown with an answer to the backend feedback endpoint.
- Added deterministic coverage for the 700 ms edit debounce and final source handling.

### Changed

- Changed text responses to update one Telegram message through throttled `editMessageText` calls instead of emitting a message per chunk.
- Changed final answer rendering to attach 👍/👎 buttons after the final chunk and associate them with the persisted backend message id.
- Updated the README with the root Compose flow, SSE behavior, debounce interval, and source-aware feedback contract.

### Verified

- Verified real Bot API polling as `@frolls_bot`, backend connectivity, and handled RAG message updates against the running Compose stack.
- Verified feedback source submission to the backend and PostgreSQL persistence.
- Verified the final bot suite: `14 passed`.

## [2026-07-03]

### Added

- Added admin command router protected by `IsAdmin` at router level and `BOT_ADMIN_IDS` configuration.
- Added `/stats`, `/users`, and `/broadcast <text>` commands backed by the backend `/chats/admin/*` API and `X-Admin-Token`.
- Added inline 👍/👎 feedback buttons after assistant answers and callback handling through `POST /chats/{chat_id}/messages/{message_id}/feedback`.
- Added background broadcast polling from the backend broadcast queue and per-recipient Telegram delivery.
- Added `ADMIN_TOKEN` configuration for admin API calls.

### Changed

- Changed backend SSE parsing to store the final assistant `message_id` from the `done` event for feedback callbacks.
- Changed HTTP error handling for admin and feedback flows to show readable Telegram messages instead of tracebacks.

### Verified

- Verified Docker image build through the root Compose stack.
- Verified live polling startup, backend connectivity, handled updates, and feedback persistence against the running backend.

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
