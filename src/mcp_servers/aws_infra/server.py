"""
AWS Infrastructure MCP Server.

Exposes EC2 management tools over the Model Context Protocol.
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from src.mcp_servers.aws_infra.tools import (
    describe_ec2_instance,
    diagnose_instance,
    list_ec2_instances,
    remediate_disk_full,
    remediate_high_cpu,
    remediate_high_memory,
    restart_ec2_instance,
    run_ssm_command,
)
from src.utils.aws_helpers import setup_logging

logger = setup_logging("mcp-server.aws-infra")
server = MCPServer("aws-infra-server")


@server.tool(
    name="list_ec2_instances",
    description="List EC2 instances filtered by state and/or tags.",
)
async def list_ec2_instances_tool(
    state_filter: str = "running",
    tag_filters: str = "",
    max_results: int = 50,
) -> str:
    result = await list_ec2_instances(
        state_filter=state_filter,
        tag_filters=tag_filters,
        max_results=max_results,
    )
    return json.dumps(result, indent=2, default=str)


@server.tool(
    name="describe_ec2_instance",
    description="Get detailed information about a single EC2 instance.",
)
async def describe_ec2_instance_tool(instance_id: str) -> str:
    result = await describe_ec2_instance(instance_id=instance_id)
    return json.dumps(result, indent=2, default=str)


@server.tool(
    name="restart_ec2_instance",
    description="Restart an EC2 instance after confirmation.",
)
async def restart_ec2_instance_tool(instance_id: str) -> str:
    result = await restart_ec2_instance(instance_id=instance_id)
    return json.dumps(result, indent=2, default=str)


async def run_ssm_command_tool(instance_id: str, command: str, timeout_seconds: int = 60) -> str:
    result = await run_ssm_command(
        instance_id=instance_id,
        command=command,
        timeout_seconds=timeout_seconds,
    )
    return json.dumps(result, indent=2, default=str)


async def diagnose_instance_tool(instance_id: str) -> str:
    result = await diagnose_instance(instance_id=instance_id)
    return json.dumps(result, indent=2, default=str)


async def remediate_high_cpu_tool(instance_id: str, pid: str) -> str:
    result = await remediate_high_cpu(instance_id=instance_id, pid=pid)
    return json.dumps(result, indent=2, default=str)


async def remediate_disk_full_tool(instance_id: str) -> str:
    result = await remediate_disk_full(instance_id=instance_id)
    return json.dumps(result, indent=2, default=str)


async def remediate_high_memory_tool(instance_id: str, pid: str) -> str:
    result = await remediate_high_memory(instance_id=instance_id, pid=pid)
    return json.dumps(result, indent=2, default=str)


def main() -> None:
    """Run the MCP server over stdio transport."""
    logger.info("Starting AWS Infra MCP server …")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
