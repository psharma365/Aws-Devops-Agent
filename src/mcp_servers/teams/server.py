"""
Microsoft Teams MCP Server.

Exposes notification tools over the Model Context Protocol.
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from src.mcp_servers.teams.tools import (
    create_incident_notification,
    send_teams_message,
)
from src.utils.aws_helpers import setup_logging

logger = setup_logging("mcp-server.teams")
server = MCPServer("teams-server")


@server.tool(name="send_teams_message")
async def send_teams_message_tool(message: str) -> str:
    """Send a plain-text message to the configured Microsoft Teams channel."""
    result = await send_teams_message(message=message)
    return json.dumps(result, indent=2, default=str)


@server.tool(name="create_incident_notification")
async def create_incident_notification_tool(
    severity: str,
    instance_id: str,
    alarm_name: str,
    metric_value: str,
    summary: str,
    actions_taken: str = "None yet",
) -> str:
    """Send a structured incident Adaptive Card to Teams with severity,
    instance details, metric snapshot, summary, and actions taken.
    """
    result = await create_incident_notification(
        severity=severity,
        instance_id=instance_id,
        alarm_name=alarm_name,
        metric_value=metric_value,
        summary=summary,
        actions_taken=actions_taken,
    )
    return json.dumps(result, indent=2, default=str)


def main() -> None:
    """Run the MCP server over stdio transport."""
    logger.info("Starting Teams MCP server …")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
