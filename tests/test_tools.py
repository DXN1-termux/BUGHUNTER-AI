"""Unit tests for tool dispatcher."""
import pytest


def test_unknown_tool_returns_error():
    from slm.tools import dispatch
    result = dispatch("nonexistent_tool", {})
    assert "error: unknown tool" in result
    assert "nonexistent_tool" in result


def test_tool_schemas_include_all_tools():
    from slm.tools import get_tool_schemas, TOOLS
    schemas = get_tool_schemas()
    assert len(schemas) == len(TOOLS)
    for s in schemas:
        assert "name" in s
        assert "parameters" in s


def test_shell_empty_cmd_rejected():
    from slm.tools import shell
    result = shell("")
    assert "error" in result.lower()


def test_write_file_empty_path_rejected():
    from slm.tools import write_file
    result = write_file("", "content")
    assert "error" in result.lower()


def test_read_file_nonexistent():
    from slm.tools import read_file
    result = read_file("/tmp/this_file_definitely_does_not_exist_12345.txt")
    assert "error" in result.lower()


def test_needs_confirmation_mutating():
    from slm.tools import needs_confirmation
    assert needs_confirmation("shell") is True
    assert needs_confirmation("write_file") is True


def test_needs_confirmation_readonly():
    from slm.tools import needs_confirmation
    assert needs_confirmation("read_file") is False
    assert needs_confirmation("list_dir") is False


def test_needs_confirmation_unknown():
    from slm.tools import needs_confirmation
    assert needs_confirmation("nope") is False
