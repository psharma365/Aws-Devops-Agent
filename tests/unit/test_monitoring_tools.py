"""
Unit tests for CloudWatch Monitoring MCP tools.

Uses moto to mock the CloudWatch service.
"""

from __future__ import annotations

from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from src.mcp_servers.monitoring.tools import (
    get_cpu_metrics,
    get_cpu_metrics_for_instances,
    get_disk_usage,
    get_memory_metrics,
)


@pytest.fixture
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def cloudwatch_with_metrics(aws_credentials):
    """Create mocked CloudWatch with CPU metric data."""
    with mock_aws():
        cw = boto3.client("cloudwatch", region_name="us-east-1")

        # Put some CPU metric data
        cw.put_metric_data(
            Namespace="AWS/EC2",
            MetricData=[
                {
                    "MetricName": "CPUUtilization",
                    "Dimensions": [{"Name": "InstanceId", "Value": "i-0abc123def456789a"}],
                    "Timestamp": datetime.now(UTC),
                    "Value": 85.5,
                    "Unit": "Percent",
                },
            ],
        )
        yield cw


@pytest.mark.unit
class TestGetCpuMetrics:
    """Tests for the get_cpu_metrics tool."""

    @pytest.mark.asyncio
    async def test_get_cpu_metrics_returns_structure(self, cloudwatch_with_metrics):
        result = await get_cpu_metrics("i-0abc123def456789a", period=300, minutes=60)
        assert result["instance_id"] == "i-0abc123def456789a"
        assert result["metric"] == "CPUUtilization"
        assert "datapoints" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_get_cpu_metrics_empty_for_unknown(self, cloudwatch_with_metrics):
        result = await get_cpu_metrics("i-unknown", period=300, minutes=60)
        assert result["datapoints"] == []
        assert result["summary"]["datapoint_count"] == 0


@pytest.mark.unit
class TestBatchCpuMetrics:
    """Tests for the get_cpu_metrics_for_instances tool."""

    @pytest.mark.asyncio
    async def test_batch_metrics(self, cloudwatch_with_metrics):
        result = await get_cpu_metrics_for_instances(
            instance_ids=["i-0abc123def456789a", "i-unknown"],
            period=300,
            minutes=60,
        )
        assert result["instance_count"] == 2
        assert "i-0abc123def456789a" in result["results"]
        assert "i-unknown" in result["results"]


@pytest.mark.unit
class TestMemoryAndDisk:
    """Tests for memory and disk tools (stub behaviour without CW Agent)."""

    @pytest.mark.asyncio
    async def test_get_memory_metrics_no_agent(self, cloudwatch_with_metrics):
        result = await get_memory_metrics("i-0abc123def456789a")
        # Without CW Agent data, expect empty datapoints
        assert result["instance_id"] == "i-0abc123def456789a"

    @pytest.mark.asyncio
    async def test_get_disk_usage_no_agent(self, cloudwatch_with_metrics):
        result = await get_disk_usage("i-0abc123def456789a", mount_path="/")
        assert result["instance_id"] == "i-0abc123def456789a"


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "args"),
    [
        (get_cpu_metrics, ("i-test",)),
        (get_cpu_metrics_for_instances, (["i-test"],)),
        (get_memory_metrics, ("i-test",)),
        (get_disk_usage, ("i-test",)),
    ],
)
@pytest.mark.parametrize(
    ("period", "minutes", "message"),
    [
        (0, 60, "period must be a positive number of seconds"),
        (-1, 60, "period must be a positive number of seconds"),
        (300, 0, "minutes must be a positive number"),
        (300, -1, "minutes must be a positive number"),
    ],
)
async def test_metric_tools_reject_non_positive_windows_without_cloudwatch(
    monkeypatch,
    tool,
    args,
    period,
    minutes,
    message,
):
    def unexpected_cloudwatch_client(_service: str):
        raise AssertionError("CloudWatch client should not be created for invalid windows")

    monkeypatch.setattr("src.mcp_servers.monitoring.tools.get_client", unexpected_cloudwatch_client)

    result = await tool(*args, period=period, minutes=minutes)

    assert result == {
        "error": True,
        "code": "ValidationError",
        "message": message,
    }
