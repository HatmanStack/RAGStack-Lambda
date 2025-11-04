"""Tests for ConfigurationTable seeding with chat fields."""
import sys
from unittest.mock import MagicMock, patch

# Mock boto3 and botocore in sys.modules before importing publish
sys.modules['boto3'] = MagicMock()
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()

from publish import seed_configuration_table


def test_chat_schema_has_required_fields():
    """Verify chat schema includes all required fields."""
    # Mock DynamoDB table
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            # Mock CloudFormation describe_stacks
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            # Mock DynamoDB table
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Call function
            seed_configuration_table('test-stack', 'us-east-1')

            # Get the schema item that was put
            calls = mock_table.put_item.call_args_list
            schema_call = calls[0]
            schema_item = schema_call[1]['Item']

            # Verify chat fields exist
            props = schema_item['Schema']['properties']
            assert 'chat_require_auth' in props
            assert 'chat_primary_model' in props
            assert 'chat_fallback_model' in props
            assert 'chat_global_quota_daily' in props
            assert 'chat_per_user_quota_daily' in props
            assert 'chat_theme_preset' in props
            assert 'chat_theme_overrides' in props


def test_chat_default_values():
    """Verify default configuration has correct chat values."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            seed_configuration_table('test-stack', 'us-east-1')

            # Get the default item
            calls = mock_table.put_item.call_args_list
            default_call = calls[1]
            default_item = default_call[1]['Item']

            # Verify defaults
            assert default_item['chat_require_auth'] is False
            assert default_item['chat_primary_model'] == 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
            assert default_item['chat_fallback_model'] == 'us.amazon.nova-micro-v1:0'
            assert default_item['chat_global_quota_daily'] == 10000
            assert default_item['chat_per_user_quota_daily'] == 100
            assert default_item['chat_theme_preset'] == 'light'
            assert default_item['chat_theme_overrides'] == {}


def test_chat_theme_preset_enum():
    """Verify theme preset has correct enum values."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            seed_configuration_table('test-stack', 'us-east-1')

            calls = mock_table.put_item.call_args_list
            schema_item = calls[0][1]['Item']

            theme_enum = schema_item['Schema']['properties']['chat_theme_preset']['enum']
            assert theme_enum == ['light', 'dark', 'brand']


def test_chat_deployed_flag_default():
    """Verify chat_deployed defaults to False."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Call without chat_deployed argument
            seed_configuration_table('test-stack', 'us-east-1')

            calls = mock_table.put_item.call_args_list
            default_item = calls[1][1]['Item']

            assert default_item['chat_deployed'] is False


def test_chat_deployed_flag_true():
    """Verify chat_deployed can be set to True."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Call with chat_deployed=True
            seed_configuration_table('test-stack', 'us-east-1', chat_deployed=True)

            calls = mock_table.put_item.call_args_list
            default_item = calls[1][1]['Item']

            assert default_item['chat_deployed'] is True
