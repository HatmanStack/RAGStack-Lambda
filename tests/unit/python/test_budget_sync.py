"""Unit tests for budget_sync Lambda."""

import importlib.util
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_budget_sync_module():
    """Load the budget_sync index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src" / "lambda" / "budget_sync" / "index.py"
    ).resolve()

    if "budget_sync_index" in sys.modules:
        del sys.modules["budget_sync_index"]

    spec = importlib.util.spec_from_file_location("budget_sync_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["budget_sync_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    with patch.dict(
        os.environ,
        {
            "BUDGET_NAME": "test-budget",
            "ADMIN_EMAIL": "admin@example.com",
            "PROJECT_NAME": "test-project",
        },
    ):
        yield


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.log_stream_name = "test-log-stream"
    return ctx


class TestGetDynamodbValue:
    """Tests for get_dynamodb_value function."""

    @patch("boto3.client")
    def test_extracts_number(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_budget_sync_module()
        result = module.get_dynamodb_value({"threshold": {"N": "100"}}, "threshold")
        assert result == Decimal("100")

    @patch("boto3.client")
    def test_extracts_string(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_budget_sync_module()
        result = module.get_dynamodb_value({"name": {"S": "test"}}, "name")
        assert result == "test"

    @patch("boto3.client")
    def test_extracts_bool(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_budget_sync_module()
        result = module.get_dynamodb_value({"enabled": {"BOOL": True}}, "enabled")
        assert result is True

    @patch("boto3.client")
    def test_missing_key_returns_default(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_budget_sync_module()
        result = module.get_dynamodb_value({}, "missing", default="fallback")
        assert result == "fallback"

    @patch("boto3.client")
    def test_null_value(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_budget_sync_module()
        result = module.get_dynamodb_value({"field": {"NULL": True}}, "field")
        assert result is None


class TestProcessRecord:
    """Tests for process_record function."""

    @patch("boto3.client")
    def test_skips_non_custom_config(self, mock_boto3_client):
        mock_budgets = MagicMock()
        mock_sts = MagicMock()
        mock_boto3_client.side_effect = lambda svc, **_kw: {
            "budgets": mock_budgets,
            "sts": mock_sts,
        }[svc]

        module = load_budget_sync_module()
        record = {
            "eventName": "MODIFY",
            "dynamodb": {
                "Keys": {"Configuration": {"S": "Default"}},
                "NewImage": {},
                "OldImage": {},
            },
        }

        module.process_record(record)
        mock_budgets.update_budget.assert_not_called()

    @patch("boto3.client")
    def test_skips_delete_event(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_budget_sync_module()
        record = {
            "eventName": "REMOVE",
            "dynamodb": {"Keys": {"Configuration": {"S": "Custom"}}},
        }
        module.process_record(record)  # Should not raise

    @patch("boto3.client")
    def test_threshold_change_updates_budget(self, mock_boto3_client):
        mock_budgets = MagicMock()
        mock_budgets.describe_budget.return_value = {
            "Budget": {"TimeUnit": "MONTHLY", "BudgetType": "COST", "CostFilters": {}}
        }
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789"}
        mock_boto3_client.side_effect = lambda svc, **_kw: {
            "budgets": mock_budgets,
            "sts": mock_sts,
        }[svc]

        module = load_budget_sync_module()
        with (
            patch.object(module, "budgets", mock_budgets),
            patch.object(module, "sts", mock_sts),
        ):
            module._account_id = None  # Reset cache
            record = {
                "eventName": "MODIFY",
                "dynamodb": {
                    "Keys": {"Configuration": {"S": "Custom"}},
                    "NewImage": {
                        "Configuration": {"S": "Custom"},
                        "budget_alert_threshold": {"N": "200"},
                        "budget_alert_enabled": {"BOOL": True},
                    },
                    "OldImage": {
                        "Configuration": {"S": "Custom"},
                        "budget_alert_threshold": {"N": "100"},
                        "budget_alert_enabled": {"BOOL": True},
                    },
                },
            }
            module.process_record(record)

        mock_budgets.update_budget.assert_called_once()

    @patch("boto3.client")
    def test_disabled_sets_high_threshold(self, mock_boto3_client):
        mock_budgets = MagicMock()
        mock_budgets.describe_budget.return_value = {
            "Budget": {"TimeUnit": "MONTHLY", "BudgetType": "COST", "CostFilters": {}}
        }
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789"}
        mock_boto3_client.side_effect = lambda svc, **_kw: {
            "budgets": mock_budgets,
            "sts": mock_sts,
        }[svc]

        module = load_budget_sync_module()
        with (
            patch.object(module, "budgets", mock_budgets),
            patch.object(module, "sts", mock_sts),
        ):
            module._account_id = None
            record = {
                "eventName": "MODIFY",
                "dynamodb": {
                    "Keys": {"Configuration": {"S": "Custom"}},
                    "NewImage": {
                        "Configuration": {"S": "Custom"},
                        "budget_alert_enabled": {"BOOL": False},
                    },
                    "OldImage": {
                        "Configuration": {"S": "Custom"},
                        "budget_alert_enabled": {"BOOL": True},
                    },
                },
            }
            module.process_record(record)

        # Should update with 999999 threshold
        call_kwargs = mock_budgets.update_budget.call_args[1]
        assert call_kwargs["NewBudget"]["BudgetLimit"]["Amount"] == "999999"


class TestUpdateBudget:
    """Tests for update_budget and create_budget."""

    @patch("boto3.client")
    def test_creates_budget_when_not_found(self, mock_boto3_client):
        class NotFoundError(Exception):
            pass

        mock_budgets = MagicMock()
        mock_budgets.exceptions.NotFoundException = NotFoundError
        mock_budgets.describe_budget.side_effect = NotFoundError("not found")
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789"}
        mock_boto3_client.side_effect = lambda svc, **_kw: {
            "budgets": mock_budgets,
            "sts": mock_sts,
        }[svc]

        module = load_budget_sync_module()
        with (
            patch.object(module, "budgets", mock_budgets),
            patch.object(module, "sts", mock_sts),
        ):
            module._account_id = None
            module.update_budget(100.0)

        mock_budgets.create_budget.assert_called_once()


class TestLambdaHandler:
    """Tests for lambda_handler."""

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_cfn_delete_sends_success(self, mock_boto3_client, mock_urlopen, mock_context):
        mock_boto3_client.return_value = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_budget_sync_module()
        event = {
            "RequestType": "Delete",
            "ResponseURL": "https://cfn.example.com",
            "StackId": "arn:aws:cloudformation:us-east-1:123:stack/test/guid",
            "RequestId": "req-123",
            "LogicalResourceId": "BudgetSync",
        }

        result = module.lambda_handler(event, mock_context)
        assert result["statusCode"] == 200

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"

    @patch("boto3.client")
    def test_dynamodb_stream_event(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()

        module = load_budget_sync_module()
        event = {
            "Records": [
                {
                    "eventName": "MODIFY",
                    "dynamodb": {
                        "Keys": {"Configuration": {"S": "Default"}},
                        "NewImage": {},
                        "OldImage": {},
                    },
                }
            ]
        }

        result = module.lambda_handler(event, None)
        assert result["statusCode"] == 200

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_cfn_unhandled_error_sends_failed(self, mock_boto3_client, mock_urlopen, mock_context):
        mock_boto3_client.return_value = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_budget_sync_module()
        # Patch _handle_event to raise to test global exception handler
        with patch.object(module, "_handle_event", side_effect=RuntimeError("boom")):
            event = {
                "RequestType": "Create",
                "ResponseURL": "https://cfn.example.com",
                "StackId": "arn:aws:cloudformation:us-east-1:123:stack/test/guid",
                "RequestId": "req-123",
                "LogicalResourceId": "BudgetSync",
            }
            result = module.lambda_handler(event, mock_context)

        assert result["statusCode"] == 500
        # Should still send FAILED response to CFN
        assert mock_urlopen.call_count >= 1
