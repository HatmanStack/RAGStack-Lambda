"""Shared AWS clients for query_kb package.

Lazy-initialized boto3 clients reused across warm Lambda invocations.
Imported by other modules in the package.
"""

from typing import Any

import boto3

_s3_client: Any = None
_dynamodb: Any = None
_dynamodb_client: Any = None
_bedrock_agent: Any = None
_bedrock_runtime: Any = None


def _get_s3_client() -> Any:
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _get_dynamodb() -> Any:
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _get_dynamodb_client() -> Any:
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


def _get_bedrock_agent() -> Any:
    global _bedrock_agent
    if _bedrock_agent is None:
        _bedrock_agent = boto3.client("bedrock-agent-runtime")
    return _bedrock_agent


def _get_bedrock_runtime() -> Any:
    global _bedrock_runtime
    if _bedrock_runtime is None:
        _bedrock_runtime = boto3.client("bedrock-runtime")
    return _bedrock_runtime


# Module-level proxy objects for backwards compatibility.
# Other modules import these names; the __getattr__ pattern lets us
# keep the same import interface while deferring boto3.client() calls.
class _LazyProxy:
    """Proxy that defers client creation until first attribute access."""

    def __init__(self, factory: Any) -> None:
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_client", None)

    def _resolve(self) -> Any:
        client = object.__getattribute__(self, "_client")
        if client is None:
            factory = object.__getattribute__(self, "_factory")
            client = factory()
            object.__setattr__(self, "_client", client)
        return client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve()(*args, **kwargs)


s3_client = _LazyProxy(_get_s3_client)
dynamodb = _LazyProxy(_get_dynamodb)
dynamodb_client = _LazyProxy(_get_dynamodb_client)
bedrock_agent = _LazyProxy(_get_bedrock_agent)
bedrock_runtime = _LazyProxy(_get_bedrock_runtime)
