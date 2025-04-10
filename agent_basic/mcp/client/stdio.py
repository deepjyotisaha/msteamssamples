# agent_basic/mcp/client/stdio.py
import asyncio
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class StdioServerParameters:
    command: str
    args: List[str]

async def stdio_client(params: StdioServerParameters) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Create a connection to a stdio server"""
    process = await asyncio.create_subprocess_exec(
        params.command,
        *params.args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    return process.stdout, process.stdin