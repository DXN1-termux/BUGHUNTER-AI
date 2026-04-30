"""Encrypted secrets vault — passphrase-protected credential storage.

© 2026 DXN10DAY · BUGHUNTER-AI v2.3 · MIT + PPL-1.0 + UAAC-1.1

Every secret (Discord token, Anthropic key, OpenAI key, webhook, etc.) is
encrypted with Fernet (AES-128 CBC + HMAC-SHA256) using a key derived from
your passphrase via PBKDF2-HMAC-SHA256 (600k rounds).

File layout:
    ~/.slm/vault.enc        — ciphertext only, never contains plaintext
    ~/.slm/vault.salt       — per-install salt (16 random bytes)

Privacy guarantees:
  - The passphrase is never stored on disk.
  - The passphrase never appears in memory longer than needed to derive a key.
  - Secrets are never logged, traced, or sent to the model.
  - If ~/.slm/vault.enc leaks, without the passphrase it's gibberish.
  - `slm panic` securely shreds it.

Auto-lock: after 15 minutes of idle, the in-memory key is wiped.
"""
from __future__ import annotations
import base64, json, os, pathlib, secrets, time
from typing import Optional

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
VAULT = SLM_HOME / "vault.enc"
SALT = SLM_HOME / "vault.salt"
IDLE_LOCK_SECONDS = 900   # 15 minutes

# In-memory state (NEVER persisted)
_cached_key: Optional[bytes] = None
_last_use: float = 0.0


class VaultLocked(RuntimeError):
    pass


class VaultWrongPassphrase(RuntimeError):
    pass


def _require_crypto():
    try:
        from cryptography.fernet import Fernet, InvalidToken
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        return Fernet, InvalidToken, hashes, PBKDF2HMAC
    except ImportError:
        raise RuntimeError(
            "vault needs the `cryptography` package: pip install cryptography"
        )


def _load_or_create_salt() -> bytes:
    SLM_HOME.mkdir(parents=True, exist_ok=True)
    if SALT.exists():
        return SALT.read_bytes()
    salt = secrets.token_bytes(16)
    SALT.write_bytes(salt)
    # best-effort chmod; won't matter on non-POSIX
    try:
        os.chmod(SALT, 0o600)
    except OSError:
        pass
    return salt


def _derive(passphrase: str) -> bytes:
    Fernet, _, hashes, PBKDF2HMAC = _require_crypto()
    salt = _load_or_create_salt()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=600_000)
    raw = kdf.derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def unlock(passphrase: str) -> None:
    """Derive the key and cache it. Verifies by attempting a decrypt if vault exists."""
    global _cached_key, _last_use
    Fernet, InvalidToken, _, _ = _require_crypto()
    key = _derive(passphrase)
    if VAULT.exists():
        try:
            Fernet(key).decrypt(VAULT.read_bytes())
        except InvalidToken:
            raise VaultWrongPassphrase("wrong passphrase")
    _cached_key = key
    _last_use = time.time()


def lock() -> None:
    """Wipe the in-memory key."""
    global _cached_key, _last_use
    if _cached_key is not None:
        # Best-effort overwrite
        try:
            _cached_key = bytes(len(_cached_key))
        except Exception:
            pass
    _cached_key = None
    _last_use = 0.0


def _require_unlocked() -> bytes:
    global _last_use
    if _cached_key is None:
        raise VaultLocked("vault is locked — run: slm vault unlock")
    if time.time() - _last_use > IDLE_LOCK_SECONDS:
        lock()
        raise VaultLocked("vault auto-locked after idle timeout")
    _last_use = time.time()
    return _cached_key


def _read() -> dict:
    if not VAULT.exists():
        return {}
    key = _require_unlocked()
    Fernet, _, _, _ = _require_crypto()
    raw = Fernet(key).decrypt(VAULT.read_bytes())
    return json.loads(raw.decode("utf-8"))


def _write(data: dict) -> None:
    key = _require_unlocked()
    Fernet, _, _, _ = _require_crypto()
    ct = Fernet(key).encrypt(json.dumps(data).encode("utf-8"))
    SLM_HOME.mkdir(parents=True, exist_ok=True)
    # Atomic replace
    tmp = VAULT.with_suffix(".enc.tmp")
    tmp.write_bytes(ct)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, VAULT)


def is_unlocked() -> bool:
    return _cached_key is not None and (time.time() - _last_use) <= IDLE_LOCK_SECONDS


def exists() -> bool:
    return VAULT.exists()


def set_secret(name: str, value: str) -> None:
    data = _read()
    data[name] = value
    _write(data)


def get_secret(name: str) -> Optional[str]:
    data = _read()
    return data.get(name)


def delete_secret(name: str) -> bool:
    data = _read()
    if name not in data:
        return False
    del data[name]
    _write(data)
    return True


def list_secrets() -> list[dict]:
    """Returns [{name, length, preview}] — NEVER the raw secret."""
    data = _read()
    return [
        {"name": n,
         "length": len(v),
         "preview": v[:4] + "…" + v[-4:] if len(v) > 10 else "***"}
        for n, v in sorted(data.items())
    ]


# ------------------------------------------------------------- redaction
def redact(text: str) -> str:
    """Strip any known vault secret from `text`. Used on every log write.
    Safe to call while locked — just does nothing in that case.
    """
    if not is_unlocked():
        return text
    try:
        data = _read()
    except Exception:
        return text
    for secret in data.values():
        if secret and len(secret) >= 8 and secret in text:
            text = text.replace(secret, "«REDACTED»")
    return text
