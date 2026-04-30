# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Enforcement Mechanisms (non-IP-ban design)

This project does NOT maintain server-side IP bans — it's 100 % local, there's no central server to ban from. Instead, enforcement works at two layers:

### 1. Local device quarantine

Every hard-block audit record includes a **device-level fingerprint** derived via `HMAC-SHA256(audit_key, uuid.getnode())`. This:

- **Is stable per device** (same MAC → same hash)
- **Is NOT portable** (each install has its own audit key, so the same MAC on a different install produces a different hash)
- **Reveals nothing to leaks** (without the audit key, the hash is random-looking)

After **3 criminal-category hard-blocks** (CSAM / terrorism / CBRN / mass-harm) from the same device in **24 hours**, the agent enters a **1-hour cooldown** where it refuses ALL requests. A file at `~/.slm/quarantine.flag` records the expiry.

Why this instead of IP ban:
- IPs are shared / dynamic / VPN-able → high false-positive rate, easy to evade
- MAC fingerprinting is device-stable → better signal
- We only store the HMAC, not the raw MAC → privacy-preserving
- Quarantine is soft: a user can `rm ~/.slm/audit.key` to reset (same as reinstall) — this is deliberate, as the goal is friction against casual abuse, not absolute lockout

Adult-content (Part B of UAAC) violations do NOT count toward quarantine — only the 4 criminal categories.

### 2. Discord bot auto-ban

When the Discord bot mode catches a user posting CSAM / terrorism / CBRN / mass-harm content:

1. The message is deleted immediately
2. The attempt is audit-logged with HMAC hashes
3. If `auto_ban_on_hard_block: true` in `discord_scope.yaml` (default **true**), the offending user is banned from the guild with 1 day of message deletion

This catches the case where the agent is operating as a 24/7 server moderator — the server owner doesn't want to manually review every removed message. The 4 criminal categories trigger auto-ban; adult-content violations only delete the message.

---

## 100% Privacy by Design

Everything runs locally. No telemetry. No phone-home. All user data is
either plaintext on your disk (traces, findings) or **encrypted** (vault).

### Data classification

| Data | Where | Encryption | Leakable? |
|------|-------|:----------:|:---------:|
| Chat history | `~/.slm/traces.db` | plaintext | only with disk access |
| Findings | `~/.slm/findings.db` | plaintext | only with disk access |
| Provenance chain | `~/.slm/provenance.jsonl` | plaintext (hash-only content) | hash-only, no PII |
| Hard-block audit | `~/.slm/traces/hardblock.log` | **HMAC-SHA256** (keyed) | hash-only + key-protected |
| Canary log | `~/.slm/canary_log.jsonl` | **HMAC-SHA256** (keyed) | hash-only + key-protected |
| Audit HMAC key | `~/.slm/audit.key` | raw (chmod 600) | delete to unlink all past audits |
| **Secrets (Discord tokens, API keys, etc.)** | `~/.slm/vault.enc` | **AES-128-CBC + HMAC + PBKDF2-SHA256** | **useless without passphrase** |

### What we never do

- Send any user data to an external server (unless you explicitly call `ask_cloud`)
- Log vault contents to traces
- Write secrets to stdout/stderr
- Retain the vault passphrase longer than needed to derive the key
- Include PII in any outbound network request
- **Let the agent rewrite its own guardrails** (see below)

### Agent self-modification limits

This project is agentic — the agent can and does rewrite its own code and
prompts via the self-improvement loop. But there's a hardcoded list of
safety-critical files it can **never** write to, even with full `write_file`
access, `--yolo`, or a custom skill:

| Category | Files |
|----------|-------|
| Safety modules | `executor_guards.py`, `scope_enforcer.py`, `hard_blocks.yaml`, `canary.py`, `refusal.py`, `vault.py`, `provenance.py` |
| Safety state | `FREEZE`, `audit.key`, `vault.enc`, `vault.salt`, `canary_log.jsonl`, `provenance.jsonl`, `traces/hardblock.log` |
| Security docs | `SECURITY.md`, `CODE_OF_CONDUCT.md` |
| CI workflows | `.github/workflows/*`, `.github/ISSUE_TEMPLATE/*` |
| System paths | `~/.ssh/`, `/etc`, `/sys`, `/proc`, `/dev` |

This list is **hardcoded in Python** (`slm/core/executor_guards.py::_is_forbidden`),
not loaded from config. Editing it requires editing the source and rebuilding.

Even for *allowed* files like `system.md`, a content sanity check rejects
any proposal that removes the hard-block keywords (`terrorism`, `CBRN`,
`CSAM`, `mass`). So the agent can evolve its prompt — but never to weaken
the 4 hard-block categories.

**Why this matters:** without this lock, a prompt-injected or jailbroken
agent could rewrite `hard_blocks.yaml` to empty, rewrite `system.md` to
remove refusal language, or touch `FREEZE` to bypass your kill switch.
With this lock: the agent can rewrite everything it needs to improve
(skills, tools, system prompt, scope, its own training data) but cannot
touch the 7 safety modules or the 7 safety state files that actually
enforce the rules.

### What you should do

- Full-disk encryption on your laptop/phone (FDE on Linux, FileVault on macOS, BitLocker on Windows, Android native encryption for Termux)
- Strong passphrase for the vault (passphrase, not a 6-digit PIN)
- `slm vault lock` when stepping away
- `slm panic --hard` if you need to destroy everything in an emergency

### Threat model

**Protected against:**
- Passive disk imaging (vault encrypted)
- Prompt injection via tool results (canary detector)
- Bounty-platform duplicate disputes (hash-chain provenance)
- Accidental disclosure of hard-block categories (immutable regex layer)

**NOT protected against:**
- Live memory inspection while vault is unlocked (key in RAM)
- Compromised host OS
- Malicious dependencies (you trust what you install)
- Side-channel attacks on the CPU

For threat models requiring stronger guarantees, run inside an air-gapped VM / dedicated device.

---

## Zero-Tolerance: CSAM

Child Sexual Abuse Material (CSAM) detection is the **highest-priority** hard block in this project, with defense-in-depth:

1. **Hardcoded patterns** in `slm/core/executor_guards.py` — fire even if `hard_blocks.yaml` is missing, corrupted, or tampered with
2. **YAML patterns** with 9 separate regex rules covering terminology, euphemisms, codewords (pthc, loli, etc.), age-explicit numeric patterns, and AI-generation requests
3. **Unicode normalization** (NFKC + leetspeak folding) defeats `cs4m`, fullwidth `ｃｓａｍ`, dotted `c.s.a.m`, mathematical alphanumerics, and zero-width separators
4. **Scanned on 5 surfaces**: user input, model output, tool results, filenames/paths, and tool arguments
5. **30+ red-team test cases** in `eval/redteam.jsonl` + unit tests in `tests/test_safety.py`

**If you encounter real CSAM anywhere** — not from this tool, in the wild — report it to:
- **US**: [NCMEC CyberTipline](https://report.cybertip.org) (1-800-843-5678)
- **EU**: [INHOPE hotlines](https://www.inhope.org/EN/articles/report-here)
- **NL**: [Offlimits](https://www.offlimits.nl)

Do not attempt to preserve evidence yourself — law enforcement will handle chain of custody.

---

## Reporting a Vulnerability

**Do NOT open a public issue for security vulnerabilities.**

Instead, please report them via:
- [GitHub Security Advisories](https://github.com/DXN1-termux/BUGHUNTER-AI/security/advisories/new)
- [WhatsApp](https://wa.me/31639420421) (direct, <24h response)

### What to include

- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)

### Response timeline

- **Acknowledgement**: within 48 hours
- **Initial assessment**: within 7 days
- **Fix release**: within 30 days for critical issues

## Security Architecture

BUGHUNTER-AI has a layered defensive design:

1. **Immutable core** (`slm/core/`) — chmod 444, never writable by the self-improvement loop
2. **Hard blocks** — regex patterns for terrorism, CBRN, CSAM, mass harm (cannot be disabled)
3. **Scope enforcement** — all network tools gated by explicit `scope.yaml`
4. **Shell denylist** — destructive commands blocked even if the model requests them
5. **Path sandbox** — prevents reads/writes to `/etc`, `/proc`, `~/.ssh`, core/
6. **Rate limiter** — sliding window + loop detector prevents runaway tool execution
7. **FREEZE switch** — instant kill switch, creates `~/.slm/FREEZE` to halt all tools
8. **Eval-gated self-improvement** — prompt/skill changes must pass functional + red-team eval

## Scope of Authorized Use

This tool is designed for **authorized security testing only**. Users must:

- Only target systems they have explicit written authorization to test
- Configure `scope.yaml` before any network operations
- Comply with all applicable laws and bug-bounty program rules

## Known Limitations

- The hard-block regex patterns are not exhaustive — they catch common phrasings
- The shell denylist is defense-in-depth, not a sandbox replacement
- The 0.5B model can be prompt-injected; the runtime guards (not the model) are the security boundary
