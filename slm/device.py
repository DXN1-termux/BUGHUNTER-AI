"""Device-class detection for model-tier selection.

Classifies the host into one of three tiers:

  mobile       → Termux (Android), iOS iSH/a-Shell, or any box with < 4 GB RAM
  desktop      → Laptop/PC, 4–23 GB RAM, no GPU
  workstation  → GPU present (CUDA/ROCm/Apple-Silicon Metal) OR ≥ 24 GB RAM

Callers use `detect().tier` to pick `[model.<tier>]` from config.toml.
"""
from __future__ import annotations
import os, platform, shutil, subprocess
from dataclasses import dataclass


@dataclass
class Device:
    tier: str            # mobile | desktop | workstation
    ram_mb: int
    cores: int
    has_gpu: bool
    platform: str        # mobile | linux | macos | windows | unknown


def _ram_mb() -> int:
    # Linux / Termux / WSL
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    # macOS
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"], text=True, timeout=2
        ).strip()
        return int(out) // (1024 * 1024)
    except Exception:
        pass
    # Windows
    if platform.system() == "Windows":
        try:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys // (1024 * 1024)
        except Exception:
            pass
    return 2048  # conservative fallback


def _has_gpu() -> bool:
    for b in ("nvidia-smi", "rocm-smi"):
        if shutil.which(b):
            return True
    # Apple Silicon → Metal
    if platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64"):
        return True
    return False


def _platform() -> str:
    # Termux detection
    if os.environ.get("PREFIX", "").endswith("com.termux/files/usr"):
        return "mobile"
    if "ANDROID_ROOT" in os.environ or "TERMUX_VERSION" in os.environ:
        return "mobile"
    # iOS (iSH, a-Shell)
    if os.environ.get("SIMULATOR_DEVICE_NAME"):
        return "mobile"
    uname = platform.platform().lower()
    if "iphone" in uname or "ipad" in uname or uname.startswith("ios"):
        return "mobile"
    sysname = platform.system()
    return {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(
        sysname, "unknown"
    )


def detect() -> Device:
    ram_mb = _ram_mb()
    cores = os.cpu_count() or 1
    has_gpu = _has_gpu()
    plat = _platform()

    if plat == "mobile" or ram_mb < 4096:
        tier = "mobile"
    elif has_gpu or ram_mb >= 24576:
        tier = "workstation"
    else:
        tier = "desktop"
    return Device(tier=tier, ram_mb=ram_mb, cores=cores,
                  has_gpu=has_gpu, platform=plat)
