"""llm.py: API key resolution. Covers Entry #31 — the blank-shell-var regression.

`has_api_key()`/`_client()` must find `.env` even when a shell profile has
already exported the same variable name blank (or stale) — python-dotenv
defaults to `override=False`, which would otherwise make a real `.env` key
invisible behind a pre-existing empty environment variable.

`find_dotenv()`'s default search walks up from the *caller's own file
location* (here, `llm.py`'s directory), not from cwd — so these tests can't
isolate a fake `.env` via `monkeypatch.chdir`; they would always resolve to
this repo's real `.env`. Instead, `dotenv.load_dotenv` is replaced with a
fake that reproduces real override semantics faithfully, so what's actually
under test is the one thing that matters: which `override` value `llm.py`
passes.
"""

from __future__ import annotations

import dotenv
import pytest

import creativesignal.llm as llm


DOTENV_VALUE = "sk-ant-real-key-from-dotenv"


def _fake_load_dotenv(*, override=False, **kwargs):
    """Reproduce python-dotenv's real override rule for one variable.

    Mirrors the actual bug: a pre-existing environment variable is left
    alone unless the caller explicitly asks to override it.
    """
    import os

    if override or "ANTHROPIC_API_KEY" not in os.environ:
        os.environ["ANTHROPIC_API_KEY"] = DOTENV_VALUE
    return True


@pytest.fixture(autouse=True)
def fake_dotenv(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", _fake_load_dotenv)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_has_api_key_true_when_dotenv_provides_it(monkeypatch):
    assert llm.has_api_key() is True


def test_blank_shell_export_does_not_shadow_a_real_dotenv_key(monkeypatch):
    """Entry #31: a shell profile exporting `ANTHROPIC_API_KEY=""` (a real,
    observed ~/.zshrc pattern) must not permanently hide a valid `.env` key.

    Without `override=True`, python-dotenv treats an already-present blank
    variable as "already set" and refuses to load `.env` over it — exactly
    the reported symptom: a correct `.env` file, silently ignored.
    """
    import os

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert llm.has_api_key() is True
    assert os.environ["ANTHROPIC_API_KEY"] == DOTENV_VALUE


def test_stale_shell_export_is_also_overridden(monkeypatch):
    """Not just blank — any pre-existing value must defer to `.env`, since a
    stale exported key is just as wrong as an empty one."""
    import os

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stale-from-a-different-project")
    assert llm.has_api_key() is True
    assert os.environ["ANTHROPIC_API_KEY"] == DOTENV_VALUE


def test_has_api_key_calls_load_dotenv_with_override_true(monkeypatch):
    """Pin the actual fix: the call site must pass override=True explicitly.

    A regression that quietly drops the kwarg would pass every other test
    here (the fake defaults to False, matching real dotenv), so the call
    itself is asserted directly.
    """
    calls = []
    monkeypatch.setattr(
        dotenv, "load_dotenv", lambda **kw: calls.append(kw) or True
    )
    llm.has_api_key()
    assert calls == [{"override": True}]


# --- endpoint pinning (Entry #39) -----------------------------------------
# The SDK reads ANTHROPIC_BASE_URL from the environment. A shell profile
# pointing it at a proxy silently redirects every call in the project, and
# surfaces as an *authentication* error that blames the key.


def test_shell_base_url_cannot_redirect_the_client(monkeypatch):
    """Regression: ~/.zshrc exported ANTHROPIC_BASE_URL=openrouter, which sent
    Anthropic-keyed requests to a proxy expecting Bearer auth -> 401
    'Missing Authentication header'."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
    assert llm._base_url() == llm.DEFAULT_BASE_URL


def test_base_url_defaults_to_anthropic_when_unset(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    assert llm._base_url() == "https://api.anthropic.com"


def test_dotenv_can_still_set_a_deliberate_proxy(tmp_path, monkeypatch):
    """Pinning must not remove the supported way to point at a proxy."""
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_BASE_URL=https://proxy.example/v1\n")
    monkeypatch.setattr(llm, "_base_url", llm._base_url)  # keep the real fn
    monkeypatch.setattr(
        "dotenv.find_dotenv", lambda *a, **k: str(env)
    )
    assert llm._base_url() == "https://proxy.example/v1"


def test_client_is_built_with_the_pinned_base_url(monkeypatch):
    """The pin must reach the constructed client, not just the helper."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-value")
    llm._client.cache_clear()
    client = llm._client()
    assert str(client.base_url).rstrip("/") == llm.DEFAULT_BASE_URL
    # An Anthropic key must go out as x-api-key, never a Bearer token.
    assert "X-Api-Key" in client.auth_headers
    llm._client.cache_clear()
