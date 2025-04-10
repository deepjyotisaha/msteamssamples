# agent_basic/mcp/client/__init__.py
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class ClientSession:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    async def initialize(self):
        """Initialize the session"""
        pass

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools"""
        return {"tools": []}

    async def close(self):
        """Close the session"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

from .stdio import StdioServerParameters, stdio_client

__all__ = ['ClientSession', 'StdioServerParameters', 'stdio_client']