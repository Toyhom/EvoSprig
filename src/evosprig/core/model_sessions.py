"""Optional provider lifetimes without coupling the runtime to an adapter."""

from contextlib import AsyncExitStack, asynccontextmanager


@asynccontextmanager
async def model_sessions(providers):
    """Share a provider session across a run and release it on every exit path."""
    async with AsyncExitStack() as stack:
        seen = set()
        for provider in providers:
            if id(provider) in seen:
                continue
            seen.add(id(provider))
            session = getattr(provider, "session", None)
            if session is not None:
                await stack.enter_async_context(session())
        yield
