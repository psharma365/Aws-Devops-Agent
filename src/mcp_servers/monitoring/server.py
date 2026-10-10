"""
CloudWatch Monitoring MCP Server.

Exposes metrics retrieval tools over the Model Context Protocol.
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from src.mcp_servers.monitoring.tools import (
    get_cpu_metrics,
    get_cpu_metrics_for_instances,
    get_disk_usage,
    get_memory_metrics,
)
from src.utils.aws_helpers import setup_logging

logger = setup_logging("mcp-server.monitoring")
server = MCPServer("monitoring-server")


@server.tool(name="get_cpu_metrics")
async def get_cpu_metrics_tool(
    instance_id: str,
    period: int = 300,
    minutes: int = 60,
) -> str:
    """Retrieve CPU utilization metrics for a single EC2 instance over a time window."""
    result = await get_cpu_metrics(
        instance_id=instance_id,
        period=period,
        minutes=minutes,
    )
    return json.dumps(result, indent=2, default=str)


@server.tool(name="get_cpu_metrics_for_instances")
async def get_cpu_metrics_for_instances_tool(
    instance_ids: list[str],
    period: int = 300,
    minutes: int = 60,
) -> str:
    """Batch-retrieve CPU utilization for multiple instances in one call."""
    result = await get_cpu_metrics_for_instances(
        instance_ids=instance_ids,
        period=period,
        minutes=minutes,
    )
    return json.dumps(result, indent=2, default=str)


@server.tool(name="get_memory_metrics")
async def get_memory_metrics_tool(
    instance_id: str,
    period: int = 300,
    minutes: int = 60,
) -> str:
    """Retrieve memory utilization for an instance (requires CloudWatch Agent)."""
    result = await get_memory_metrics(
        instance_id=instance_id,
        period=period,
        minutes=minutes,
    )
    return json.dumps(result, indent=2, default=str)


@server.tool(name="get_disk_usage")
async def get_disk_usage_tool(
    instance_id: str,
    mount_path: str = "/",
    period: int = 300,
    minutes: int = 60,
) -> str:
    """Retrieve disk usage metrics for an instance (requires CloudWatch Agent)."""
    result = await get_disk_usage(
        instance_id=instance_id,
        mount_path=mount_path,
        period=period,
        minutes=minutes,
    )
    return json.dumps(result, indent=2, default=str)


def main() -> None:
    """Run the MCP server over stdio transport."""
    logger.info("Starting Monitoring MCP server …")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
