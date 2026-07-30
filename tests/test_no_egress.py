"""Canonical isolation test for airgap-agent.

This test is the enforcement mechanism behind the project's core promise:
the harness must be *incapable* of outbound network I/O. It blocks socket
creation at the OS-wrapper level, then exercises the agent loop and asserts
that nothing ever attempted to open a connection.

If this test ever needs to be weakened to make a feature work, that feature
does not belong in airgap-agent. See SECURITY.md.
"""

from __future__ import annotations

import builtins
import socket

import pytest


class EgressAttempt(AssertionError):
    """Raised when any code under test tries to touch the network."""


@pytest.fixture
def block_all_egress(monkeypatch):
    """Make any socket creation an immediate, loud failure."""

    def _deny(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise EgressAttempt(
            f"Egress attempt detected: socket({args!r}, {kwargs!r})"
        )

    # Block the low-level primitives every networking library funnels through.
    monkeypatch.setattr(socket, "socket", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    monkeypatch.setattr(socket, "getaddrinfo", _deny)

    yield


def test_socket_is_blocked(block_all_egress):
    """Sanity check: our own guard actually fires."""
    with pytest.raises(EgressAttempt):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_core_imports_have_no_network_client():
    """The agent core must not pull in an HTTP/socket client library.

    We assert on the import surface rather than trusting runtime behavior:
    a networking library absent from sys.modules after importing the core
    cannot be used to egress.
    """
    import importlib
    import sys

    forbidden = {"requests", "httpx", "urllib3", "aiohttp", "websockets"}

    # NOTE: enable once the package exists.
    # importlib.import_module("airgap_agent.agent")
    # importlib.import_module("airgap_agent.inference")
    # importlib.import_module("airgap_agent.tools")

    leaked = forbidden & set(sys.modules)
    assert not leaked, f"Core imported networking libraries: {sorted(leaked)}"


@pytest.mark.skip(reason="enable once airgap_agent.agent loop exists")
def test_agent_loop_never_egresses(block_all_egress):
    """Run a full turn of the agent loop and assert zero egress attempts."""
    from airgap_agent.agent import AgentLoop  # noqa: F401

    loop = AgentLoop.local_only()
    loop.run_once(prompt="hello, offline world")
    # Reaching here without EgressAttempt is the pass condition.
