"""Platform-polymorphic context manager."""
from __future__ import annotations
import os
import sys
import platform
import pathlib
from abc import ABC, abstractmethod

class PlatformContext(ABC):
    @abstractmethod
    def get_system_root(self) -> pathlib.Path:
        pass

    @abstractmethod
    def get_sensitive_paths(self) -> list[pathlib.Path]:
        pass

    @abstractmethod
    def is_shell_command_safe(self, cmd: str) -> bool:
        pass

class TermuxContext(PlatformContext):
    def get_system_root(self) -> pathlib.Path:
        return pathlib.Path("/data/data/com.termux/files/usr")

    def get_sensitive_paths(self) -> list[pathlib.Path]:
        home = pathlib.Path.home()
        return [
            home / ".ssh",
            home / ".config/gh",
            home / ".env",
            home / ".git",
            pathlib.Path("/etc"),
            pathlib.Path("/sys"),
            pathlib.Path("/proc"),
            pathlib.Path("/dev")
        ]

    def is_shell_command_safe(self, cmd: str) -> bool:
        # Termux-specific shell restrictions
        return True

class MacOSContext(PlatformContext):
    def get_system_root(self) -> pathlib.Path:
        return pathlib.Path("/")

    def get_sensitive_paths(self) -> list[pathlib.Path]:
        home = pathlib.Path.home()
        return [
            home / ".ssh",
            pathlib.Path("/etc"),
            pathlib.Path("/System"),
            pathlib.Path("/Library")
        ]

    def is_shell_command_safe(self, cmd: str) -> bool:
        return True

def get_context() -> PlatformContext:
    if os.environ.get("PREFIX", "").startswith("/data/data/com.termux"):
        return TermuxContext()
    if sys.platform == "darwin":
        return MacOSContext()
    # Default to a generic Linux context or raise error
    raise NotImplementedError(f"Unsupported platform: {sys.platform}")
