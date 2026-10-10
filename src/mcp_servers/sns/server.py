"""
AWS SNS MCP Server.

Exposes alerting tools with Teams-to-SNS failover over the
Model Context Protocol.
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from src.mcp_servers.sns.tools import request_approval, send_alert_with_failover
from src.utils.aws_helpers import setup_logging

logger = setup_logging("mcp-server.sns")
server = MCPServer("sns-server")


@server.tool(
    name="send_alert_with_failover",
    description="Send an alert to Teams and fail over to AWS SNS if needed.",
)
async def send_alert_with_failover_tool(subject: str, message: str) -> str:
    result = await send_alert_with_failover(subject=subject, message=message)
    return json.dumps(result, indent=2, default=str)


@server.tool(
    name="request_approval",
    description="Request human approval for a MAJOR remediation action.",
)
async def request_approval_tool(
    instance_id: str,
    action_type: str,
    reason: str,
    details: str = "",
) -> str:
    result = await request_approval(
        instance_id=instance_id,
        action_type=action_type,
        reason=reason,
        details=details,
    )
    return json.dumps(result, indent=2, default=str)


def main() -> None:
    logger.info("Starting SNS MCP server …")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
