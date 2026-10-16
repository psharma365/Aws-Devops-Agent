"""Unit tests for the Lambda alarm handler."""

from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

import src.handlers.lambda_handler as lambda_handler


class StubTable:
    def __init__(self, error_code: str | None = None) -> None:
        self.error_code = error_code
        self.request: dict[str, object] | None = None

    def put_item(self, **request: object) -> None:
        self.request = request
        if self.error_code:
            raise ClientError(
                {"Error": {"Code": self.error_code, "Message": "stubbed error"}},
                "PutItem",
            )


@pytest.mark.unit
def test_claim_alarm_writes_an_atomic_claim(monkeypatch):
    table = StubTable()
    monkeypatch.setattr(lambda_handler, "_dedup_table", table)
    monkeypatch.setattr(lambda_handler.time, "time", lambda: 1_700_000_000)

    assert lambda_handler._claim_alarm("cpu-high") is False

    assert table.request is not None
    assert table.request["Item"] == {
        "approval_id": "alarm_dedup:cpu-high",
        "processed_at": 1_700_000_000,
        "ttl": 1_700_003_600,
    }
    assert "ConditionExpression" in table.request
    assert table.request["ExpressionAttributeValues"] == {
        ":cutoff": 1_700_000_000 - lambda_handler.DEDUP_WINDOW
    }


@pytest.mark.unit
def test_claim_alarm_reports_recent_alarm_as_duplicate(monkeypatch, capsys):
    table = StubTable(error_code="ConditionalCheckFailedException")
    monkeypatch.setattr(lambda_handler, "_dedup_table", table)

    assert lambda_handler._claim_alarm("cpu-high") is True
    assert "skipping" in capsys.readouterr().out


@pytest.mark.unit
def test_claim_alarm_fails_open_when_dynamodb_is_unavailable(monkeypatch, capsys):
    table = StubTable(error_code="InternalServerError")
    monkeypatch.setattr(lambda_handler, "_dedup_table", table)

    assert lambda_handler._claim_alarm("cpu-high") is False
    assert "proceeding anyway" in capsys.readouterr().out


@pytest.mark.unit
def test_handler_includes_alarm_category_in_agent_prompt(monkeypatch, sample_alarm_event):
    prompts: list[str] = []
    monkeypatch.setattr(lambda_handler, "_claim_alarm", lambda _alarm_name: False)
    monkeypatch.setattr(
        lambda_handler,
        "_invoke_agentcore",
        lambda prompt: prompts.append(prompt) or {"error": False, "response": "ok"},
    )

    response = lambda_handler.handler(sample_alarm_event, None)

    assert response["statusCode"] == 200
    assert "Alarm category: cpu" in prompts[0]


@pytest.mark.unit
def test_handler_returns_error_when_aws_credentials_are_unavailable(monkeypatch, sample_alarm_event):
    class SessionWithoutCredentials:
        def __init__(self, region_name: str) -> None:
            self.region_name = region_name

        def get_credentials(self) -> None:
            return None

    monkeypatch.setattr(lambda_handler.boto3, "Session", SessionWithoutCredentials)
    monkeypatch.setattr(lambda_handler, "_claim_alarm", lambda _alarm_name: False)

    response = lambda_handler.handler(sample_alarm_event, None)

    assert response["statusCode"] == 500
    assert "AWS credentials are unavailable" in response["body"]
