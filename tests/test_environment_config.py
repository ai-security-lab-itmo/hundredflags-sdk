"""Environment configuration precedence and compatibility with existing credentials."""

import inspect
from typing import Any

import httpx
import pytest

import hundredflags_sdk as sdk
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


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("token_options", [{}, {"token": None}])
@pytest.mark.parametrize("environment_name", ["HUNDREDFLAGS_TOKEN", "AI_SECURITY_SCHOOL_TOKEN"])
async def test_constructor_reads_environment_when_token_is_omitted_or_none(
    client_type: Any,
    token_options: dict[str, None],
    environment_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(environment_name, "env-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer env-token"
        return httpx.Response(200, json={"instances": []})

    client = client_type(**token_options, transport=httpx.MockTransport(handler))
    try:
        assert await invoke(client.envs.list) == []
    finally:
        await invoke(client.close)


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("use_factory", [False, True])
@pytest.mark.parametrize("token", ["", " secret", "secret\n", "кириллица", 123, False])
def test_invalid_explicit_token_never_falls_back_to_environment(
    client_type: Any,
    use_factory: bool,
    token: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HUNDREDFLAGS_TOKEN", "env-token")
    constructor = client_type.from_env if use_factory else client_type
    with pytest.raises(ConfigurationError, match="Set HUNDREDFLAGS_TOKEN"):
        constructor(token=token)


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("use_factory", [False, True])
@pytest.mark.parametrize("token_options", [{}, {"token": None}])
def test_missing_token_fails_during_client_creation(
    client_type: Any, use_factory: bool, token_options: dict[str, None]
) -> None:
    constructor = client_type.from_env if use_factory else client_type
    with pytest.raises(ConfigurationError, match="Set HUNDREDFLAGS_TOKEN"):
        constructor(**token_options)


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("configured_token", ["new-token", ""])
async def test_constructor_prefers_explicit_then_new_environment_token(
    client_type: Any, configured_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUNDREDFLAGS_TOKEN", configured_token)
    monkeypatch.setenv("AI_SECURITY_SCHOOL_TOKEN", "old-token")
    received: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request.headers["Authorization"])
        return httpx.Response(200, json={"instances": []})

    client = client_type("explicit-token", transport=httpx.MockTransport(handler))
    try:
        assert await invoke(client.envs.list) == []
    finally:
        await invoke(client.close)
    assert received == ["Bearer explicit-token"]

    if not configured_token:
        with pytest.raises(ConfigurationError):
            client_type()
        return

    client = client_type(transport=httpx.MockTransport(handler))
    try:
        assert await invoke(client.envs.list) == []
    finally:
        await invoke(client.close)
    assert received[-1] == "Bearer new-token"
