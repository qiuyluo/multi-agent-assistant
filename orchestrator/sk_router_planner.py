from agents.literature_agent import run_literature_agent_stream
from typing import AsyncGenerator

async def multi_agent_dispatch_stream(user_input: str) -> AsyncGenerator[str, None]:
    async for token in run_literature_agent_stream(user_input):
        if token is None or not isinstance(token, str):
            print(f"[multi_agent_dispatch_stream] Skipping invalid token: {repr(token)}")
            continue
        yield token