# Privacy Preservation License (PPL-1.0)

**Alongside the MIT License covering the code, this document is a binding
commitment from the project maintainer and a condition of distribution
for any derivative work.**

## 1. Purpose

BUGHUNTER-AI is designed from the ground up to run on the user's own
hardware, using the user's own compute, with the user's data staying on
the user's disk. This license documents that commitment in writing and
makes it a condition of redistribution.

## 2. Architectural Privacy Guarantees

The following properties are enforced in code and verified by the test
suite in `tests/`. Any derivative work that redistributes under the name
BUGHUNTER-AI (or a trivial variation) MUST preserve all of them:

### 2.1 Zero telemetry
No network call is made by the core runtime except:
- calls to the user's own local `llama-server` on 127.0.0.1
- calls to services the user explicitly configures (Snowflake, cloud
  passthrough with the user's own API key, Discord bot to the user's
  authorized guilds, recon targets listed in the user's `scope.yaml`)

No analytics, no pingbacks, no crash reports, no usage statistics leave
the user's machine without the user's explicit per-call authorization.

### 2.2 Secrets at rest are encrypted
All credentials stored by the runtime (API keys, bot tokens, webhook URLs)
are protected by:
- AES-128-CBC with HMAC-SHA256 authentication (Fernet)
- A key derived via PBKDF2-HMAC-SHA256 with **≥ 600,000 iterations**
- A per-install random 16-byte salt
- chmod 600 on all key/vault files

If the user's vault file leaks without the passphrase, the ciphertext is
computationally infeasible to decrypt.

### 2.3 Audit logs are hash-only and keyed
The hard-block and canary forensic logs store only:
- HMAC-SHA256 keyed hashes (using a per-install 32-byte key)
- Timestamp, category, surface label, and byte length

No raw user input, no raw model output, and no raw tool-result content is
ever written to any audit log. Even with the log file leaked, a dictionary
attack against it requires also capturing the separate audit key file.

### 2.4 Session redaction
Any session trace written to disk is filtered to remove known vault
secrets before persistence.

### 2.5 User-controlled destruction
`slm panic` and `slm panic --hard` are always available; the user can
overwrite and delete all runtime state at any time. No "undelete" or
"recovery" backdoor exists.

### 2.6 No hidden network access
The agent CANNOT make arbitrary outbound network calls. Every network
tool (`fetch_url`, `nmap`, `nuclei`, `httpx`, etc.) is gated by the user's
`scope.yaml`. Any target not listed there is rejected at the
`check_target()` layer before any packet is sent.

### 2.7 No phone-home on updates
Version checks, update notifications, and "improvement" pings are
prohibited. The user initiates every update manually.

## 3. Compliance with the Privacy Commitment

Derivative works that:
- Add telemetry without opt-in consent
- Reduce PBKDF2 iteration count below 600,000
- Replace HMAC audit hashes with plain hashes
- Log raw secrets or raw blocked content
- Add hidden network calls
- Weaken or remove the panic-shred capability

MAY NOT be distributed under the name "BUGHUNTER-AI", "BUGHUNTER", or
"slm-agent", and MUST clearly disclose the weakening in their own
documentation.

## 4. Relationship to MIT

The MIT License in `LICENSE` grants broad permissions to use, copy,
modify, merge, publish, distribute, sublicense, and sell the Software.
This Privacy Preservation License does not restrict those rights. It
documents the architectural guarantees that make the privacy claim true
and prohibits using the project's brand for software that silently
weakens them.

## 5. Enforcement

This license is enforced by:
1. The test suite (removing a guarantee fails the tests)
2. The hardcoded forbidden-path list in `slm/core/executor_guards.py`
3. Pull-request review against the guidelines in `CONTRIBUTING.md`
4. Public disclosure of violations

Reports of violations may be sent to the maintainer via
`SECURITY.md`'s reporting channels.

---

*PPL-1.0 · 2026 · MIT-compatible addendum.*
