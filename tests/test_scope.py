"""Unit tests for scope enforcement."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def scope_file(tmp_path, monkeypatch):
    sf = tmp_path / "scope.yaml"
    sf.write_text(yaml.dump({
        "domains": ["example.com", "*.authorized.test"],
        "ips": ["10.0.0.0/24"],
    }))
    monkeypatch.setenv("SLM_HOME", str(tmp_path))
    import importlib
    import slm.core.scope_enforcer
    importlib.reload(slm.core.scope_enforcer)
    return sf


def test_scope_allows_bare_domain(scope_file):
    from slm.core.scope_enforcer import check_target
    check_target("example.com")


def test_scope_allows_subdomain(scope_file):
    from slm.core.scope_enforcer import check_target
    check_target("api.example.com")


def test_scope_allows_url(scope_file):
    from slm.core.scope_enforcer import check_target
    check_target("https://api.example.com/path")


def test_scope_blocks_unknown_domain(scope_file):
    from slm.core.scope_enforcer import check_target, OutOfScopeError
    with pytest.raises(OutOfScopeError):
        check_target("google.com")


def test_scope_wildcard_subdomain_only(scope_file):
    from slm.core.scope_enforcer import check_target, OutOfScopeError
    check_target("sub.authorized.test")
    with pytest.raises(OutOfScopeError):
        check_target("authorized.test")


def test_scope_ip_in_cidr(scope_file):
    from slm.core.scope_enforcer import check_target
    check_target("10.0.0.5")


def test_scope_ip_out_of_cidr(scope_file):
    from slm.core.scope_enforcer import check_target, OutOfScopeError
    with pytest.raises(OutOfScopeError):
        check_target("8.8.8.8")


def test_scope_url_with_port(scope_file):
    from slm.core.scope_enforcer import check_target
    check_target("http://api.example.com:8080/")
