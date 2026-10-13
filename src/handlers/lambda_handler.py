"""
AWS Lambda handler — EventBridge to DevOps Agent via AgentCore Runtime.

Includes DynamoDB-based deduplication to prevent the same alarm from
triggering multiple agent invocations (and multiple emails).
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "ap-southeast-2")
AGENT_RUNTIME_ARN = os.environ.get(
    "AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:ap-southeast-2:650251690796:runtime/devops_agent-AYHFY5ECcy"
)
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
APPROVALS_TABLE = os.environ.get("APPROVALS_TABLE", "devops-agent-approvals")

# Deduplication window — skip if the same alarm was processed within this period
DEDUP_WINDOW = int(os.environ.get("DEDUP_WINDOW_SECONDS", "600"))  # 10 minutes

# Computed once at cold-start from AGENT_RUNTIME_ARN env var.
# If the ARN changes (e.g. CDK redeploy), a new Lambda cold start will pick it up.
_encoded_arn = quote(AGENT_RUNTIME_ARN, safe="")
AGENTCORE_INVOKE_URL = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{_encoded_arn}/invocations"

_sns = boto3.client("sns", region_name=REGION)
_ddb = boto3.resource("dynamodb", region_name=REGION)
_dedup_table = _ddb.Table(APPROVALS_TABLE)


# ── Alarm parsing ────────────────────────────────────────────────────────


def _parse_alarm(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("detail", {})
    config = detail.get("configuration", {})
    metrics = config.get("metrics", [{}])
    metric_stat = metrics[0].get("metricStat", {}) if metrics else {}
    metric = metric_stat.get("metric", {})
    dimensions = metric.get("dimensions", {})
    state = detail.get("state", {})
    return {
        "alarm_name": detail.get("alarmName", ""),
        "state": state.get("value", "UNKNOWN"),
        "reason": state.get("reason", ""),
        "timestamp": state.get("timestamp", event.get("time", "")),
        "region": event.get("region", ""),
        "instance_id": dimensions.get("InstanceId", ""),
    }


def _detect_alarm_type(alarm_name: str) -> str:
    name_lower = alarm_name.lower()
    if "cpu" in name_lower:
        return "cpu"
    elif "mem" in name_lower:
        return "memory"
    elif "disk" in name_lower:
        return "disk"
    return "unknown"


# ── Deduplication ────────────────────────────────────────────────────────


def _claim_alarm(alarm_name: str) -> bool:
    """Atomically claim an alarm unless it was processed within DEDUP_WINDOW."""
    now = int(time.time())
    dedup_key = f"alarm_dedup:{alarm_name}"
    try:
        _dedup_table.put_item(
            Item={
                "approval_id": dedup_key,
                "processed_at": now,
                "ttl": now + 3600,
            },
            ConditionExpression=(
                "attribute_not_exists(approval_id) "
                "OR attribute_not_exists(processed_at) "
                "OR processed_at <= :cutoff"
            ),
            ExpressionAttributeValues={":cutoff": now - DEDUP_WINDOW},
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            print(f"DEDUP: {alarm_name} was processed within {DEDUP_WINDOW}s, skipping")
            return True
        print(f"DEDUP claim failed (proceeding anyway): {exc}")
    except Exception as exc:
        print(f"DEDUP claim failed (proceeding anyway): {exc}")

    return False


# ── Agent invocation ─────────────────────────────────────────────────────


def _invoke_agentcore(prompt: str) -> dict[str, Any]:
    # Fetch fresh credentials on every invocation to avoid expiry in warm Lambdas
    session_credentials = boto3.Session(region_name=REGION).get_credentials()
    if session_credentials is None:
        raise RuntimeError("AWS credentials are unavailable; cannot sign the AgentCore request")
    credentials = session_credentials.get_frozen_credentials()

    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    request = AWSRequest(method="POST", url=AGENTCORE_INVOKE_URL, data=payload)
    request.headers["Content-Type"] = "application/json"
    SigV4Auth(credentials, "bedrock-agentcore", REGION).add_auth(request)

    http_request = urllib.request.Request(
        url=AGENTCORE_INVOKE_URL,
        data=payload,
        headers=dict(request.headers),
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=300) as resp:
            body = resp.read().decode("utf-8")
            print(f"AgentCore response: status={resp.status}, len={len(body)}")
            return {"status": resp.status, "response": body, "error": False}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8") if e.fp else str(e)
        print(f"AgentCore HTTP error: {e.code} - {err[:500]}")
        return {"status": e.code, "response": err, "error": True, "message": err}
    except Exception as e:
        print(f"AgentCore failed: {e}")
        return {"status": 500, "response": "", "error": True, "message": str(e)}


# ── Handler ──────────────────────────────────────────────────────────────


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    print(f"Lambda invoked: {json.dumps(event, default=str)[:500]}")

    alarm = _parse_alarm(event)
    print(f"Parsed: name={alarm['alarm_name']} instance={alarm['instance_id']} state={alarm['state']}")

    # Only process ALARM state — ignore OK / INSUFFICIENT_DATA transitions
    if alarm["state"] != "ALARM":
        print(f"Ignoring non-ALARM state: {alarm['state']}")
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ignored", "state": alarm["state"]}),
        }

    # Deduplication — skip if this alarm was already processed recently
    if _claim_alarm(alarm["alarm_name"]):
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "deduplicated", "alarm": alarm["alarm_name"]}),
        }

    alarm_type = _detect_alarm_type(alarm["alarm_name"])

    prompt = (
        f"A CloudWatch alarm fired for instance {alarm['instance_id']}.\n"
        f"Alarm: {alarm['alarm_name']}. Reason: {alarm['reason']}. "
        f"State: {alarm['state']}. Timestamp: {alarm['timestamp']}.\n"
        f"Alarm category: {alarm_type}. Investigate this alarm and take appropriate action following your runbook."
    )

    print(f"Invoking AgentCore: {AGENTCORE_INVOKE_URL[:80]}")
    result = _invoke_agentcore(prompt)

    if result.get("error"):
        return {
            "statusCode": result.get("status", 500),
            "body": json.dumps({"error": result.get("message")}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "alarm_name": alarm["alarm_name"],
                "agent_response": result.get("response", "")[:2000],
            }
        ),
    }
