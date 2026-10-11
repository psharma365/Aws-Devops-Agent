"""
Unit tests for the EventBridge event parser.
"""

from __future__ import annotations

import pytest

from src.handlers.event_parser import (
    build_agent_prompt_from_alarm,
    parse_eventbridge_alarm,
)


@pytest.mark.unit
class TestParseEventBridgeAlarm:
    """Tests for parse_eventbridge_alarm."""

    def test_parse_valid_alarm(self, sample_alarm_event):
        alarm = parse_eventbridge_alarm(sample_alarm_event)
        assert alarm.alarm_name == "devops-agent-high-cpu"
        assert alarm.state == "ALARM"
        assert alarm.previous_state == "OK"
        assert alarm.instance_id == "i-0abc123def456789a"
        assert alarm.metric_name == "CPUUtilization"
        assert alarm.namespace == "AWS/EC2"
        assert alarm.threshold == 80.0
        assert alarm.region == "us-east-1"

    def test_parse_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Unsupported event source"):
            parse_eventbridge_alarm({"source": "aws.s3"})

    def test_parse_empty_detail_raises(self):
        with pytest.raises(ValueError, match="no 'detail'"):
            parse_eventbridge_alarm({"source": "aws.cloudwatch", "detail": {}})

    def test_parse_handles_dict_metrics_and_top_level_instance_id(self):
        event = {
            "source": "aws.cloudwatch",
            "region": "us-east-1",
            "account": "123456789012",
            "detail": {
                "alarmName": "disk-usage-high",
                "alarmDescription": "Disk is full",
                "state": {"value": "ALARM", "reason": "Threshold crossed"},
                "previousState": {"value": "OK"},
                "instanceId": "i-9876543210",
                "configuration": {
                    "threshold": 90,
                    "comparisonOperator": "GreaterThanThreshold",
                    "evaluationPeriods": 1,
                    "metrics": {
                        "metricStat": {
                            "metric": {
                                "namespace": "CWAgent",
                                "name": "disk_used_percent",
                                "dimensions": {"InstanceId": "i-9876543210"},
                            },
                            "period": 300,
                        }
                    },
                },
            },
        }

        alarm = parse_eventbridge_alarm(event)
        assert alarm.instance_id == "i-9876543210"
        assert alarm.metric_name == "disk_used_percent"
        assert alarm.namespace == "CWAgent"
        assert alarm.state == "ALARM"
        assert alarm.period == 300


@pytest.mark.unit
class TestBuildAgentPrompt:
    """Tests for build_agent_prompt_from_alarm."""

    def test_build_prompt_contains_key_info(self, sample_alarm_event):
        alarm = parse_eventbridge_alarm(sample_alarm_event)
        prompt = build_agent_prompt_from_alarm(alarm)
        assert "i-0abc123def456789a" in prompt
        assert "devops-agent-high-cpu" in prompt
        assert "CRITICAL" in prompt
        assert "CPUUtilization" in prompt
        assert "send_alert_with_failover" in prompt
