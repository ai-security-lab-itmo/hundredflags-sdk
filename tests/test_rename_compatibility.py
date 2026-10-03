"""Existing integrations keep the same types while new names take precedence."""

import importlib
import inspect
from typing import Any

import httpx
import pytest

import ai_security_school_sdk as legacy
import hundredflags_sdk as sdk
from ai_security_school_sdk.errors import AuthenticationError as LegacyAuthenticationError
from hundredflags_sdk import AsyncClient, Client, ConfigurationError


@pytest.fixture(autouse=True)
def clear_sdk_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for prefix in ("HUNDREDFLAGS", "AI_SECURITY_SCHOOL"):
        for option in ("TOKEN", "BASE_URL"):
            monkeypatch.delenv(f"{prefix}_{option}", raising=False)


async def invoke(fn: Any) -> Any:
    result = fn()
    return await result if inspect.isawaitable(result) else result


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize(
    ("environment", "expected_token", "expected_host"),
    [
        ({"HUNDREDFLAGS_TOKEN": "new-token"}, "new-token", "plgn.hundredflags.ru"),
        ({"AI_SECURITY_SCHOOL_TOKEN": "old-token"}, "old-token", "plgn.hundredflags.ru"),
        (
            {
                "AI_SECURITY_SCHOOL_TOKEN": "old-token",
                "AI_SECURITY_SCHOOL_BASE_URL": "https://old.example",
            },
            "old-token",
            "old.example",
        ),
        (
            {
                "HUNDREDFLAGS_TOKEN": "new-token",
                "HUNDREDFLAGS_BASE_URL": "https://new.example",
                "AI_SECURITY_SCHOOL_TOKEN": "old-token",
                "AI_SECURITY_SCHOOL_BASE_URL": "https://old.example",
            },
            "new-token",
            "new.example",
        ),
        (
            {
                "HUNDREDFLAGS_TOKEN": "new-token",
                "AI_SECURITY_SCHOOL_BASE_URL": "https://old.example",
            },
            "new-token",
            "old.example",
        ),
        (
            {
                "AI_SECURITY_SCHOOL_TOKEN": "old-token",
                "HUNDREDFLAGS_BASE_URL": "https://new.example",
            },
            "old-token",
            "new.example",
        ),
    ],
)
async def test_environment_name_precedence(
    client_type: Any,
    environment: dict[str, str],
    expected_token: str,
    expected_host: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {expected_token}"
        assert request.url.host == expected_host
        assert request.headers["User-Agent"] == f"hundredflags-sdk/{sdk.__version__}"
        return httpx.Response(200, json={"instances": []})

    client = client_type.from_env(transport=httpx.MockTransport(handler))
    try:
        assert await invoke(client.envs.list) == []
    finally:
        await invoke(client.close)


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("option", ["TOKEN", "BASE_URL"])
def test_empty_new_environment_value_does_not_select_legacy_identity(
    client_type: Any, option: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUNDREDFLAGS_TOKEN", "new-token")
    monkeypatch.setenv("HUNDREDFLAGS_BASE_URL", "https://new.example")
    monkeypatch.setenv("AI_SECURITY_SCHOOL_TOKEN", "old-token")
    monkeypatch.setenv("AI_SECURITY_SCHOOL_BASE_URL", "https://old.example")
    monkeypatch.setenv(f"HUNDREDFLAGS_{option}", "")
    with pytest.raises(ConfigurationError):
        client_type.from_env()


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_explicit_configuration_overrides_both_environment_names(
    client_type: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    for prefix in ("HUNDREDFLAGS", "AI_SECURITY_SCHOOL"):
        monkeypatch.setenv(f"{prefix}_TOKEN", "")
        monkeypatch.setenv(f"{prefix}_BASE_URL", "")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer explicit-token"
        assert request.url.host == "explicit.example"
        return httpx.Response(200, json={"instances": []})

    client = client_type.from_env(
        token="explicit-token",
        base_url="https://explicit.example",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert await invoke(client.envs.list) == []
    finally:
        await invoke(client.close)


def test_legacy_package_exports_same_public_objects() -> None:
    assert legacy.__version__ == sdk.__version__
    assert legacy.__all__ == sdk.__all__
    for name in sdk.__all__:
        assert getattr(legacy, name) is getattr(sdk, name)


@pytest.mark.parametrize("module_name", ["client", "async_client", "errors", "models"])
def test_legacy_submodule_exports_same_defined_public_objects(module_name: str) -> None:
    canonical_module = importlib.import_module(f"hundredflags_sdk.{module_name}")
    legacy_module = importlib.import_module(f"ai_security_school_sdk.{module_name}")
    public_objects = {
        name: value
        for name, value in vars(canonical_module).items()
        if not name.startswith("_")
        and getattr(value, "__module__", None) == canonical_module.__name__
    }
    assert public_objects
    for name, value in public_objects.items():
        assert getattr(legacy_module, name) is value


@pytest.mark.parametrize("client_type", [legacy.Client, legacy.AsyncClient])
async def test_legacy_exception_handlers_catch_canonical_transport_errors(
    client_type: Any,
) -> None:
    client = client_type(
        "test-token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                401, json={"error": {"code": "invalid_token", "message": "Expired token"}}
            )
        ),
    )
    try:
        with pytest.raises(LegacyAuthenticationError) as caught:
            await invoke(client.envs.list)
        assert isinstance(caught.value, sdk.AuthenticationError)
        assert caught.value.code == "invalid_token"
    finally:
        await invoke(client.close)
