# Changelog

## [2026-11-03]

### CI maintenance

- Pinned Ruff to the locally verified 0.15.16 and made the existing lint rule set explicit, matching backend and pre-commit. Fresh installations previously selected 0.17.3 and failed lint before running tests.

### Added

- Added separate `/clear_chat` and `/clear_agent` controls alongside full `/clear`, plus `/escalate` and `/ticket` commands for persistent backend tickets.
- Added live acceptance scripts using the real backend client and a standalone bot HTTP API without polling, with retained [verification evidence](docs/verification/README.md).
- Added Ruff checks in pre-commit/CI and documented the shared deployment configuration maintained in the backend repository.

### Changed

- Aligned full clearing with backend chat history, agent checkpoints, pending confirmation, and local FSM state.
- Updated progress/status handling for buffered chat answers and completed agent steps; documented the actual SSE behavior and confirmation flow.
- Updated backend-client integration and deployment instructions for the revised APIs and portable pair checks.

### Verified

- Recorded 39 bot tests and one cross-service smoke test with passing Ruff checks.
- Completed nine live agent turns covering memory, time tools, attributed knowledge search, preview/cancel, and full clearing. Confirmation of an obsolete request after clearing returned 409; the bot access audit recorded no `/notify` requests.
- Live checks used the real backend client and bot HTTP API without Telegram polling, broadcasts, or positive delivery confirmation; these results do not establish end-to-end Telegram delivery.

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
