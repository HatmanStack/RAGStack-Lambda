"""CloudFormation custom resource for idempotent admin user provisioning.

Creates a Cognito user only if it doesn't already exist, avoiding
CloudFormation update conflicts when redeploying stacks.
"""

import json
import logging
import urllib.request

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client("cognito-idp")


def send_response(event: dict, context, status: str, reason: str = "", data: dict = None) -> None:
    """Send response to CloudFormation."""
    response_body = {
        "Status": status,
        "Reason": reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": event.get("PhysicalResourceId", event["LogicalResourceId"]),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
    }

    body = json.dumps(response_body).encode("utf-8")

    req = urllib.request.Request(
        event["ResponseURL"],
        data=body,
        method="PUT",
        headers={"Content-Type": "", "Content-Length": len(body)},
    )

    try:
        with urllib.request.urlopen(req) as response:
            logger.info(f"CloudFormation response status: {response.status}")
    except Exception as e:
        logger.error(f"Failed to send response to CloudFormation: {e}")
        raise


def create_user(user_pool_id: str, email: str) -> dict:
    """Create user if it doesn't exist.

    Returns:
        dict with 'created' (bool) and 'username' (str)
    """
    try:
        # Check if user already exists
        response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=email)
        logger.info(f"User {email} already exists, skipping creation")
        return {"created": False, "username": response["Username"]}

    except cognito.exceptions.UserNotFoundException:
        # User doesn't exist, create it
        logger.info(f"Creating user {email}")
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            DesiredDeliveryMediums=["EMAIL"],
        )
        return {"created": True, "username": email}


def lambda_handler(event: dict, context) -> None:
    """Handle CloudFormation custom resource events."""
    logger.info(f"Event: {json.dumps(event)}")

    request_type = event["RequestType"]
    properties = event.get("ResourceProperties", {})

    user_pool_id = properties.get("UserPoolId")
    email = properties.get("Email")

    try:
        if request_type == "Create":
            if not user_pool_id or not email:
                send_response(event, context, "FAILED", "UserPoolId and Email are required")
                return

            result = create_user(user_pool_id, email)
            send_response(
                event,
                context,
                "SUCCESS",
                data={"Created": str(result["created"]), "Username": result["username"]},
            )

        elif request_type == "Update":
            # On update, just ensure user exists (same as create)
            if user_pool_id and email:
                result = create_user(user_pool_id, email)
                send_response(
                    event,
                    context,
                    "SUCCESS",
                    data={"Created": str(result["created"]), "Username": result["username"]},
                )
            else:
                send_response(event, context, "SUCCESS")

        elif request_type == "Delete":
            # Don't delete the user - they should persist
            logger.info("Delete requested - not deleting user (intentional)")
            send_response(event, context, "SUCCESS")

        else:
            send_response(event, context, "FAILED", f"Unknown request type: {request_type}")

    except ClientError as e:
        error_msg = f"AWS error: {e.response['Error']['Message']}"
        logger.error(error_msg)
        send_response(event, context, "FAILED", error_msg)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        send_response(event, context, "FAILED", str(e))
