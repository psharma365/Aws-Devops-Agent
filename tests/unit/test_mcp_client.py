"""Unit tests for MCP client tool result handling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.mcp_client.client import MCPClient


class StubSession:
    def __init__(self, result: SimpleNamespace) -> None:
        self.result = result

    async def call_tool(self, name: str, arguments: dict) -> SimpleNamespace:
        return self.result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_call_tool_returns_mcp_error_as_error_result():
    client = MCPClient()
    server = client._servers["aws-infra"]
    server.session = StubSession(
        SimpleNamespace(
            is_error=True,
            content=[SimpleNamespace(type="text", text="Instance is not managed by SSM")],
        )
    )
    client._tool_index["diagnose_instance"] = "aws-infra"

    result = await client.call_tool("diagnose_instance", {"instance_id": "i-test"})

    assert result == {"error": True, "message": "Instance is not managed by SSM"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_call_tool_uses_default_error_message_for_empty_mcp_error():
    client = MCPClient()
    server = client._servers["aws-infra"]
    server.session = StubSession(SimpleNamespace(is_error=True, content=[]))
    client._tool_index["diagnose_instance"] = "aws-infra"

    result = await client.call_tool("diagnose_instance")

    assert result == {"error": True, "message": "MCP tool diagnose_instance reported an error"}
