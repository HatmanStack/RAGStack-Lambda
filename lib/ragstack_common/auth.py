"""Authentication and authorization utilities for AppSync resolvers."""

import logging
from typing import Any

from ragstack_common.config import ConfigurationManager

logger = logging.getLogger(__name__)


def check_public_access(
    event: dict[str, Any],
    access_type: str,
    config_manager: ConfigurationManager,
) -> tuple[bool, str | None]:
    """
    Check if the request is allowed based on authentication and public access settings.

    Args:
        event: AppSync event with identity information
        access_type: Type of access to check ('chat', 'search', 'upload', 'image_upload')
        config_manager: ConfigurationManager instance for reading config values

    Returns:
        tuple: (allowed: bool, error_message: str or None)
    """
    identity = event.get("identity") or {}

    # Check auth type
    # 1. Cognito User Pools: identity has "sub" or "username"
    # 2. API key: identity is empty/None (considered authenticated for server-side use)
    # 3. IAM unauthenticated: identity has "cognitoIdentityAuthType" == "unauthenticated"

    has_cognito_auth = bool(identity.get("sub") or identity.get("username"))
    is_api_key = not identity  # Empty identity means API key auth
    is_unauthenticated_iam = identity.get("cognitoIdentityAuthType") == "unauthenticated"

    # If authenticated via Cognito or API key, always allow
    if has_cognito_auth or is_api_key:
        return (True, None)

    # For unauthenticated IAM, check public access config
    if is_unauthenticated_iam:
        config_key = f"public_access_{access_type}"
        public_access_allowed = config_manager.get_parameter(config_key, default=True)
        if not public_access_allowed:
            logger.info(f"Public access denied for {access_type} (unauthenticated IAM)")
            return (False, f"Authentication required for {access_type} access")

    return (True, None)
