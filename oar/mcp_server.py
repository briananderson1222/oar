"""OAR MCP Server — expose OAR tools via Model Context Protocol."""

from __future__ import annotations

import json
import sys

from oar.mcp_tools import TOOL_DEFINITIONS


def create_server():
    """Create and configure the MCP server with OAR tools."""
    try:
        from mcp.server import Server
        from mcp.types import (
            CallToolResult,
            TextContent,
            Tool,
        )
    except ImportError as exc:
        raise ImportError(
            "mcp package not installed. Install with: pip install 'oar[mcp]'"
        ) from exc

    server = Server("oar-mcp")

    @server.list_tools()
    async def list_tools():
        """List all available OAR tools."""
        tools = []
        for name, defn in TOOL_DEFINITIONS.items():
            tools.append(
                Tool(
                    name=name,
                    description=defn["description"],
                    inputSchema=defn["parameters"],
                )
            )
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """Execute an OAR tool by name with the given arguments."""
        if name not in TOOL_DEFINITIONS:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )

        handler = TOOL_DEFINITIONS[name]["handler"]

        try:
            result = handler(**arguments)
            # Convert result to JSON string for MCP response.
            if isinstance(result, (dict, list)):
                text = json.dumps(result, indent=2, default=str)
            else:
                text = str(result)

            return CallToolResult(
                content=[TextContent(type="text", text=text)],
            )
        except Exception as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {exc}")],
                isError=True,
            )

    return server


async def run_server():
    """Run the MCP server with stdio transport."""
    from mcp.server.stdio import stdio_server

    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main():
    """Entry point for `oar mcp` CLI command."""
    import asyncio

    asyncio.run(run_server())
