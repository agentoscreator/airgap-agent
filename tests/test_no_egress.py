"""Canonical isolation test for airgap-agent.

This test is the enforcement mechanism behind the project's core promise:
the harness must be *incapable* of outbound network I/O to any external
host. It intercepts socket creation, allows ONLY loopback (the sanctioned
inference path for the Ollama backup backend), and blocks everything else.

If this test ever needs to be weakened to allow a non-loopback connection,
that feature does not belong in airgap-agent. See SECURITY.md.
"""

from __future__ import annotations

import socket

import pytest

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class EgressAttempt(AssertionError):
    """Raised when code under test tries to reach a non-loopback address."""


def _host_of(address) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None


@pytest.fixture
def block_external_egress(monkeypatch):
    """Allow loopback; make any external connection a loud failure.

    We wrap connect() rather than banning sockets outright, because the
    Ollama backup backend legitimately talks to 127.0.0.1. Anything aimed
    at a non-loopback host raises EgressAttempt.
    """
    real_socket = socket.socket

    class GuardedSocket(real_socket):  # type: ignore[misc, valid-type]
        def connect(self, address):  # noqa: ANN001
            host = _host_of(address)
            if host is not None and host not in _LOOPBACK:
                raise EgressAttempt(f"External egress attempt to {address!r}")
            return super().connect(address)

        def connect_ex(self, address):  # noqa: ANN001
            host = _host_of(address)
            if host is not None and host not in _LOOPBACK:
                raise EgressAttempt(f"External egress attempt to {address!r}")
            return super().connect_ex(address)

    def _guarded_create_connection(address, *args, **kwargs):  # noqa: ANN001
        host = _host_of(address)
        if host is not None and host not in _LOOPBACK:
            raise EgressAttempt(f"External egress attempt to {address!r}")
        raise EgressAttempt(f"Unexpected create_connection to {address!r}")

    monkeypatch.setattr(socket, "socket", GuardedSocket)
    monkeypatch.setattr(socket, "create_connection", _guarded_create_connection)
    yield


def test_external_connection_is_blocked(block_external_egress):
    """Sanity check: connecting to a non-loopback host fails loudly."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(EgressAttempt):
        s.connect(("93.184.216.34", 80))  # example.com; never actually dialed
    s.close()


def test_loopback_is_allowed(block_external_egress):
    """The sanctioned inference path (loopback) must NOT be blocked."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Connecting to a closed loopback port raises ConnectionRefusedError,
        # NOT EgressAttempt — proving the guard permits loopback.
        with pytest.raises(ConnectionRefusedError):
            s.connect(("127.0.0.1", 1))
    finally:
        s.close()


def test_core_imports_have_no_external_network_client():
    """The agent core must not pull in an external HTTP/socket client.

    httpx is permitted in the tree (loopback-only Ollama backend), but the
    agent/tools core must not import it at module load.
    """
    import sys

    forbidden = {"requests", "aiohttp", "urllib3", "websockets"}

    # NOTE: enable once the package exists.
    # import importlib
    # importlib.import_module("airgap_agent.agent")
    # importlib.import_module("airgap_agent.tools")

    leaked = forbidden & set(sys.modules)
    assert not leaked, f"Core imported networking libraries: {sorted(leaked)}"


@pytest.mark.skip(reason="enable once airgap_agent.agent loop exists")
def test_agent_loop_never_egresses(block_external_egress):
    """Run a full turn of the agent loop and assert no external egress."""
    from airgap_agent.agent import AgentLoop  # noqa: F401

    loop = AgentLoop.local_only()
    loop.run_once(prompt="hello, offline world")
    # Reaching here without EgressAttempt is the pass condition.
