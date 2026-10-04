from aiogram import BaseMiddleware


class UserBackendMiddleware(BaseMiddleware):
    """Identity comes from Telegram update, never from user text/callback data."""
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if chat is not None and chat.type != "private":
            return  # private chat history and action previews must not leak to groups
        if user is None:
            return
        data["backend"] = data["backend"].for_user(str(user.id))
        return await handler(event, data)
