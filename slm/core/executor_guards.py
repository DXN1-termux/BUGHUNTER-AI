"""IMMUTABLE core — do not edit. Chmod 444 post-install.
"""IMMUTABLE core — do not edit. Chmod 444 post-install.

© 2026 DXN10DAY · BUGHUNTER-AI v2.3 · MIT + PPL-1.0 + UAAC-1.1

Enforces hard blocks, shell safety rails, path sandbox, rate limits.
Self-improvement loop MUST NOT write to this file; app/reflection.py
refuses proposals that touch slm/core/*.
"""
from __future__ import annotations
import hmac, os, re, secrets, time, hashlib, json, pathlib, shlex, unicodedata, uuid, yaml
from collections import deque
from typing import Iterable

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
CORE_DIR = pathlib.Path(__file__).parent
_HB_FILE = CORE_DIR / "hard_blocks.yaml"
_AUDIT   = SLM_HOME / "traces" / "hardblock.log"
_AUDIT_KEY = SLM_HOME / "audit.key"


def _audit_key() -> bytes:
    """Per-install random 32-byte key used as HMAC-SHA256 secret for audit hashes.

    Makes dictionary / rainbow-table attacks against audit logs infeasible:
    even if an attacker knows the string "csam" they can't compute its
    audit hash without this key.

    If the user wants maximum deniability they can `rm ~/.slm/audit.key`
    at any time — existing hashes become unlinkable to any candidate plaintext.
    """
    if _AUDIT_KEY.exists():
        return _AUDIT_KEY.read_bytes()
    _AUDIT_KEY.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    _AUDIT_KEY.write_bytes(key)
    try:
        os.chmod(_AUDIT_KEY, 0o600)
    except OSError:
        pass
    return key


def _keyed_hash(data: str) -> str:
    """HMAC-SHA256 of `data` with the per-install audit key."""
    return hmac.new(_audit_key(), data.encode("utf-8", "replace"),
                    hashlib.sha256).hexdigest()


def _device_id() -> str:
    """Privacy-preserving device fingerprint: HMAC-SHA256 of the MAC address
    (via uuid.getnode()) with the per-install audit key.

    - Stable: same device → same hash across runs.
    - Not portable: same MAC on a different install → different hash
      (because each install has its own audit key).
    - Hashed: raw MAC is never stored on disk.
    - Useless without the audit key: even with a log leak, no way to
      link the hash back to a physical MAC.

    Used for:
      - tagging audit records so repeat attempts from the same device
        are linkable locally (even across reinstalls if audit.key
        survives — user can `rm ~/.slm/audit.key` to reset)
      - triggering local quarantine after repeated hard-block attempts
    """
    try:
        mac_int = uuid.getnode()
        return _keyed_hash(f"device:{mac_int:012x}")[:16]
    except Exception:
        return "unknown"


# Local quarantine: after repeated hard-block attempts from this device in a
# short window, the agent refuses ALL requests for a cooldown period. This
# is a soft deterrent, not a security mechanism — someone persistent can
# uninstall/reinstall. But it makes casual abuse attempts much less fun.
_QUARANTINE_WINDOW_SEC = 24 * 3600    # 24 hours
_QUARANTINE_THRESHOLD = 3              # 3 hard blocks in the window
_QUARANTINE_COOLDOWN_SEC = 60 * 60     # 1 hour lockout
_QUARANTINE_FILE = SLM_HOME / "quarantine.flag"


class QuarantineActive(RuntimeError):
    """Raised when the device is currently in quarantine cooldown."""
    def __init__(self, remaining_sec: float):
        super().__init__(f"quarantine active — cooldown {int(remaining_sec)}s remaining")
        self.remaining_sec = remaining_sec


def check_quarantine() -> None:
    """Raise QuarantineActive if this device is in cooldown."""
    if not _QUARANTINE_FILE.exists():
        return
    try:
        expires_at = float(_QUARANTINE_FILE.read_text().strip())
    except (ValueError, OSError):
        return
    remaining = expires_at - time.time()
    if remaining > 0:
        raise QuarantineActive(remaining)
    # Expired — clean up
    try:
        _QUARANTINE_FILE.unlink()
    except OSError:
        pass


def _trigger_quarantine_if_repeat() -> None:
    """If this device has hit >= threshold hard-blocks in the last 24h,
    write the quarantine flag file with the cooldown expiry."""
    if not _AUDIT.exists():
        return
    device_id = _device_id()
    cutoff = time.time() - _QUARANTINE_WINDOW_SEC
    count = 0
    try:
        for line in _AUDIT.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("ts", 0) < cutoff:
                continue
            if rec.get("device_id") != device_id:
                continue
            # Only count the 4 criminal categories toward quarantine.
            # "sexual_content" policy blocks don't lock the agent — they
            # just refuse the request.
            if rec.get("category") in ("csam", "terrorism", "cbrn", "mass_harm"):
                count += 1
    except OSError:
        return
    if count >= _QUARANTINE_THRESHOLD:
        expires_at = time.time() + _QUARANTINE_COOLDOWN_SEC
        try:
            _QUARANTINE_FILE.write_text(str(expires_at))
        except OSError:
            pass


class HardBlockError(RuntimeError):
    def __init__(self, category: str, match: str):
        super().__init__(f"hard-block:{category}")
        self.category = category
        self.match = match


class LanguageGateError(HardBlockError):
    """Raised when input contains non-European scripts (Cyrillic, CJK, Arabic,
    etc.) — the most common vector for bypassing English-only regex guards.

    The agent operates in English + European languages only (Latin-script
    plus Greek and emojis). Input in other scripts is refused at the gate
    so that hard-block patterns can't be bypassed by transliteration."""
    def __init__(self, detected_scripts: list[str]):
        super().__init__("non_latin_bypass", ",".join(detected_scripts)[:80])
        self.detected_scripts = detected_scripts


# Unicode ranges allowed for the primary language gate.
# These cover every European Latin-script language + Greek + common symbols
# and emojis. Anything outside these ranges in >5% of the alphabetic chars
# is rejected.
_ALLOWED_RANGES = [
    (0x0009, 0x000D),  # tab, newline, etc.
    (0x0020, 0x007E),  # Basic Latin (ASCII printable)
    (0x00A0, 0x024F),  # Latin-1 Supplement + Latin Extended A/B
    (0x0250, 0x02FF),  # IPA Extensions + spacing modifier letters
    (0x0300, 0x036F),  # Combining Diacritical Marks (é, ñ, etc.)
    (0x0370, 0x03FF),  # Greek and Coptic (European)
    (0x1E00, 0x1EFF),  # Latin Extended Additional (Vietnamese, extended diacritics)
    (0x2000, 0x206F),  # General Punctuation (em dash, quotes, …)
    (0x2070, 0x209F),  # Super/subscripts
    (0x20A0, 0x20CF),  # Currency Symbols (€, £, ¥, etc.)
    (0x2100, 0x214F),  # Letter-like symbols (™, ©, ®)
    (0x2190, 0x21FF),  # Arrows
    (0x2200, 0x22FF),  # Math operators
    (0x2300, 0x23FF),  # Misc technical
    (0x2400, 0x243F),  # Control pictures
    (0x2500, 0x257F),  # Box drawing
    (0x2580, 0x259F),  # Block elements
    (0x25A0, 0x25FF),  # Geometric shapes
    (0x2600, 0x26FF),  # Misc symbols (☀ ☁ ⚠ etc.)
    (0x2700, 0x27BF),  # Dingbats (✓ ✗ ★ etc.)
    (0x1F300, 0x1F5FF),  # Misc symbols and pictographs (emojis)
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport + map symbols
    (0x1F700, 0x1F77F),  # Alchemical symbols
    (0x1F900, 0x1F9FF),  # Supplemental symbols (new emojis)
    (0xFE00, 0xFE0F),   # Variation selectors (emoji modifiers)
]

# Named forbidden scripts — when detected, the error message names them
# so users understand why they were refused.
_SCRIPT_NAMES = [
    ((0x0400, 0x04FF), "Cyrillic"),
    ((0x0500, 0x052F), "Cyrillic Supplement"),
    ((0x0530, 0x058F), "Armenian"),
    ((0x0590, 0x05FF), "Hebrew"),
    ((0x0600, 0x06FF), "Arabic"),
    ((0x0700, 0x074F), "Syriac"),
    ((0x0780, 0x07BF), "Thaana"),
    ((0x0900, 0x097F), "Devanagari"),
    ((0x0980, 0x09FF), "Bengali"),
    ((0x0A00, 0x0A7F), "Gurmukhi"),
    ((0x0B00, 0x0B7F), "Oriya"),
    ((0x0B80, 0x0BFF), "Tamil"),
    ((0x0C00, 0x0C7F), "Telugu"),
    ((0x0C80, 0x0CFF), "Kannada"),
    ((0x0D00, 0x0D7F), "Malayalam"),
    ((0x0E00, 0x0E7F), "Thai"),
    ((0x0E80, 0x0EFF), "Lao"),
    ((0x1000, 0x109F), "Myanmar"),
    ((0x10A0, 0x10FF), "Georgian"),
    ((0x1100, 0x11FF), "Hangul Jamo (Korean)"),
    ((0x3040, 0x309F), "Hiragana (Japanese)"),
    ((0x30A0, 0x30FF), "Katakana (Japanese)"),
    ((0x3100, 0x312F), "Bopomofo"),
    ((0x3400, 0x4DBF), "CJK Extension A"),
    ((0x4E00, 0x9FFF), "CJK Unified (Chinese)"),
    ((0xA000, 0xA4CF), "Yi Syllables"),
    ((0xAC00, 0xD7AF), "Hangul Syllables (Korean)"),
    ((0xF900, 0xFAFF), "CJK Compatibility"),
    ((0xFB00, 0xFDFF), "Arabic Presentation Forms"),
    ((0xFE70, 0xFEFF), "Arabic Presentation Forms-B"),
    ((0xFF00, 0xFFEF), "Halfwidth / Fullwidth Forms"),
    ((0x20000, 0x2A6DF), "CJK Extension B"),
]

# Homoglyph detection: these Cyrillic letters look identical to Latin but
# are different codepoints. Common bypass: typing "cаsm" with Cyrillic 'а'
# (U+0430) instead of Latin 'a' (U+0061) so the regex misses it.
# Caught at the gate because they're in the Cyrillic block — never reach here.
_HOMOGLYPH_LATIN_MAP = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "у": "y", "х": "x", "А": "A", "В": "B", "Е": "E",
    "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "У": "Y", "Х": "X",
}


def _is_allowed(ch: str) -> bool:
    cp = ord(ch)
    for lo, hi in _ALLOWED_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def _script_of(ch: str) -> str | None:
    cp = ord(ch)
    for (lo, hi), name in _SCRIPT_NAMES:
        if lo <= cp <= hi:
            return name
    return None


def check_language_gate(text: str, where: str = "input",
                        threshold: float = 0.05) -> None:
    """Reject input whose alphabetic chars are >threshold fraction non-European.

    Runs BEFORE hard-block regex so non-Latin-script bypass attempts fail
    at the gate. English, Spanish, French, German, Italian, Dutch, Polish,
    Czech, Portuguese, Romanian, Hungarian, Swedish, Norwegian, Danish,
    Finnish, Greek, and Vietnamese all pass. Russian, Chinese, Japanese,
    Korean, Arabic, Hebrew, Thai, Devanagari etc. are refused.
    """
    if not text:
        return
    # Count alphabetic chars only (numbers, spaces, punctuation are neutral)
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return
    foreign = []
    scripts_seen = set()
    for c in letters:
        if not _is_allowed(c):
            foreign.append(c)
            s = _script_of(c)
            if s:
                scripts_seen.add(s)
    if len(foreign) / len(letters) > threshold:
        # Audit the attempt using the existing HMAC keyed-hash pipeline
        _audit("non_latin_bypass", ",".join(sorted(scripts_seen))[:80], where, text)
        raise LanguageGateError(sorted(scripts_seen) or ["unknown"])


def _load_hard_blocks() -> dict:
    try:
        with _HB_FILE.open() as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict) or "categories" not in data:
            return {"categories": {}}
        return data
    except Exception:
        # If YAML is missing/corrupted/tampered, fall back to empty config.
        # The hardcoded CSAM layer below will still fire.
        return {"categories": {}}


_HB = _load_hard_blocks()
_COMPILED = {
    cat: [re.compile(p) for p in meta.get("patterns", [])]
    for cat, meta in _HB.get("categories", {}).items()
}


# -------------------------------------------------------------- CSAM tier-2 (hardcoded)
# Defense-in-depth: these patterns fire even if hard_blocks.yaml is tampered with,
# replaced, or fails to load. Zero tolerance — no config, no --yolo, no self-edit can
# disable this layer.
#
# TWO groups:
#   A. CODEWORDS — distribution/community terms with ZERO legitimate context
#      ("pthc", "loli", "raygold", etc.). Always block on bare match.
#   B. CONTEXTUAL — minor + sexual language in either order, or age-explicit
#      patterns. Always block — describing sexual content involving minors
#      is harmful regardless of framing.
#
# The acronym "CSAM" / "CP" / "child porn" itself is handled by the
# CONTEXT-AWARE smart check below (_csam_context_check), which distinguishes
# educational/defensive mentions ("what does CSAM mean") from harmful
# intent ("generate CSAM").
_CSAM_CODEWORDS = re.compile(
    r"(?i)\b("
    r"loli(con)?|shota(con)?|jailbait|pedo(phil(e|ia))?|hebephil|ephebophil|"
    r"nomap|pthc|ptsc|hurtcore|r@ygold|raygold|kinderporn|kiddie[\s-]*porn|"
    r"kid[\s-]*porn|cub[\s-]*porn"
    r")\b"
)

_CSAM_CONTEXTUAL = [
    re.compile(r"(?i)\b(child|children|minor|minors|underage|under[\s-]?18|pre[\s-]?teen|kid|toddler|infant|young\s+(girl|boy)|little\s+(girl|boy)|schoolgirl|schoolboy|teen(ager)?)\b[\s\S]{0,120}\b(sex|sexual|porn|nude|naked|nsfw|explicit|erotic|fetish|molest|lewd|undress|strip|intimate|rape)\b"),
    re.compile(r"(?i)\b(sex|sexual|porn|nude|naked|nsfw|explicit|erotic|fetish|molest|lewd|undress|strip|intimate|rape)\b[\s\S]{0,120}\b(child|minor|underage|under[\s-]?18|pre[\s-]?teen|kid|toddler|infant|young\s+(girl|boy)|little\s+(girl|boy)|schoolgirl|schoolboy|teen(ager)?)\b"),
    re.compile(r"(?i)\b(1[0-7]|[0-9])\s*(y(ear)?s?[\s-]?o(ld)?|yo)\b[\s\S]{0,80}\b(sex|porn|nude|naked|erotic|nsfw|explicit|intimate)\b"),
    re.compile(r"(?i)\b(groom|seduce|lure|entice|coerce|sextort)\b[\s\S]{0,80}\b(child|minor|kid|teen|underage|young)\b"),
]

# Context-aware: the acronym itself ("CSAM", "CSEM", "child porn", "CP")
_CSAM_TERMS = re.compile(r"(?i)\b(csam|csem|child[\s-]*porn)\b")

# Harmful-intent verbs — if paired with a CSAM term and NO defensive verb nearby, block
_CSAM_HARMFUL_VERBS = re.compile(
    r"(?i)\b("
    r"generate|create|produce|make|makes|making|cook|write|writes|writing|"
    r"compose|draft|author|render|draw|"
    r"distribute|share|shared|upload|host|seed|mirror|serve|spread|leak|"
    r"collect|obtain|find|acquire|buy|sell|trade|download|downloaded|"
    r"possess|stash|store|save|keep|"
    r"bypass|circumvent|evade|disable|weaken|remove\s+block|delete\s+filter|"
    r"jailbreak|override"
    r")\b"
)

# Defensive-intent verbs — if present alongside a CSAM term, the mention is
# treated as educational/defensive and passes the check
_CSAM_DEFENSIVE_VERBS = re.compile(
    r"(?i)\b("
    r"detect|detect\w*|block|blocks|blocking|filter|filters|filtering|"
    r"classify|classif\w*|identify|identif\w*|flag|flags|flagging|"
    r"refuse|refus\w*|scan|scans|scanning|moderate|moderat\w*|"
    r"protect|protect\w*|prevent|prevent\w*|safeguard|"
    r"report|reports|reporting|"
    r"understand|understand\w*|explain|explain\w*|define|defin\w*|"
    r"mean|means|meaning|stand\s+for|acronym|definition|"
    r"teach|teach\w*|educat\w*|research|analy\w*|study|studies|"
    r"regex|pattern|rule|filter\w*|classifier|detector|guard|"
    r"what\s+is|what\s+does|what's|"
    r"my\s+own|custom|small\s+script|defense|defensive|safety"
    r")\b"
)


def _csam_context_check(text: str) -> tuple[bool, str]:
    """Smart CSAM check that distinguishes educational/defensive mentions
    from harmful intent. Returns (should_block, matched_substring).

    Rules:
      1. Distribution codewords (pthc, loli, etc.) → ALWAYS block
      2. Contextual minor+sexual language → ALWAYS block
      3. Acronym "CSAM" alone → allow if defensive verb present
                              → block if harmful verb present and no defensive
                              → allow otherwise (model handles ambiguity)
    """
    # Rule 1: codewords with zero legitimate context
    m = _CSAM_CODEWORDS.search(text)
    if m:
        return True, m.group(0)
    # Rule 2: contextual minor-sexual patterns
    for p in _CSAM_CONTEXTUAL:
        m = p.search(text)
        if m:
            return True, m.group(0)
    # Rule 3: acronym — context-aware
    term_m = _CSAM_TERMS.search(text)
    if term_m:
        has_harmful = _CSAM_HARMFUL_VERBS.search(text)
        has_defensive = _CSAM_DEFENSIVE_VERBS.search(text)
        if has_harmful and not has_defensive:
            return True, term_m.group(0) + ":harmful_intent"
    return False, ""


def _normalize_for_scan(text: str) -> str:
    """Unicode-fold + deleetify so obfuscated variants can't bypass patterns.
    Converts: fullwidth/mathalpha -> ASCII, strips zero-widths, collapses
    whitespace, maps common leetspeak (0->o, 1->i/l, 3->e, 4->a, 5->s, 7->t,
    $->s, @->a). Intentionally lossy — only used for pattern matching, not
    displayed or stored."""
    if not text:
        return text
    # NFKC folds mathematical alphanumerics, fullwidth, compat forms
    t = unicodedata.normalize("NFKC", text)
    # Strip zero-width, BOM, format chars
    t = "".join(c for c in t if unicodedata.category(c) != "Cf")
    # Common leet substitutions (kept conservative to avoid false positives)
    leet = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
                          "7": "t", "$": "s", "@": "a", "!": "i", "|": "l"})
    t = t.translate(leet)
    # Remove visual separators often inserted to bypass regex
    t = re.sub(r"[\.\-_\*\+~`'\"\\/]+", "", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    return t


def _audit(category: str, match: str, where: str, text: str) -> None:
    """Append-only audit record. Stores HMAC-SHA256 keyed hashes only —
    no raw content, ever, and dictionary attacks are infeasible without
    the per-install audit key at ~/.slm/audit.key.

    Fields:
        ts           : timestamp
        category     : which hard-block category fired
        where        : surface (user_prompt | model_output | ...)
        match_hmac   : HMAC-SHA256(match)  first 16 hex chars
        text_hmac    : HMAC-SHA256(full text)
        text_len     : byte length

    With the audit.key deleted, these hashes are unlinkable to ANY
    candidate plaintext. With it, dictionary attacks require the key
    file itself — no precomputed rainbow table works.
    """
    _AUDIT.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "category": category,
        "where": where,
        "match_hmac": _keyed_hash(match)[:16],
        "text_hmac": _keyed_hash(text),
        "text_len": len(text),
        "device_id": _device_id(),
    }
    with _AUDIT.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    # After every audit record, check whether this device has crossed the
    # quarantine threshold. Cheap O(file size) scan on the audit log.
    try:
        _trigger_quarantine_if_repeat()
    except Exception:
        pass


def check_hard_blocks(text: str, where: str = "input") -> None:
    """Raise HardBlockError if text matches any immutable hard-block pattern.

    Defense-in-depth:
      0. Language gate (fires FIRST — non-European scripts refused at the edge)
      1. Hardcoded CSAM patterns (fires even if YAML tampered/missing)
      2. Normalized-form scan (defeats leetspeak/unicode obfuscation)
      3. YAML-loaded patterns (raw + normalized)

    Called on:
      - every user prompt before it reaches the model
      - every model output before tool execution
      - every tool RESULT fed back to the model (prompt-injection defense)
      - every filename/path the agent touches
    """
    if not text:
        return

    # Tier -1: Check device quarantine. If this device has recently
    # triggered too many hard blocks, refuse ALL requests for the cooldown.
    try:
        check_quarantine()
    except QuarantineActive as qa:
        raise HardBlockError("quarantine", f"cooldown:{int(qa.remaining_sec)}s")

    # Tier 0: language gate — refuses Cyrillic/CJK/Arabic/etc. BEFORE any
    # regex runs. Catches the most common bypass vector (transliteration).
    # Skipped on filesystem paths — Android users legitimately have files
    # with Japanese / Chinese / Arabic names in Downloads/Music/etc.
    if where != "path":
        check_language_gate(text, where=where)

    normalized = _normalize_for_scan(text)

    # Tier 1: CSAM — smart context-aware check (codewords always block,
    # acronym checked against harmful-vs-defensive intent).
    for candidate in (text, normalized):
        blocked, match = _csam_context_check(candidate)
        if blocked:
            _audit("csam", match[:80], where, text)
            raise HardBlockError("csam", match[:80])

    # Tier 2 (YAML-loaded): all configured categories on both forms
    for cat, patterns in _COMPILED.items():
        for p in patterns:
            for candidate in (text, normalized):
                m = p.search(candidate)
                if m:
                    _audit(cat, m.group(0)[:80], where, text)
                    raise HardBlockError(cat, m.group(0)[:80])


# --------------------------------------------------------------- path sandbox
# --------------------------------------------------------------- path sandbox
#
# HARDCODED FORBIDDEN LIST — cannot be disabled by config, prompt, --yolo,
# self-improvement proposals, or any agent write. This is the authoritative
# source of which paths are safety-critical. Editing this list requires
# editing the source code and rebuilding.
#
# Rule: the agent can rewrite ANYTHING EXCEPT:
#   - the guardrails themselves (slm/core/, slm/canary.py, slm/refusal.py,
#     slm/vault.py, slm/provenance.py, hard_blocks.yaml)
#   - the runtime safety state (FREEZE, audit.key, audit logs, vault files)
#   - CI workflows + SECURITY docs (so it can't silently weaken itself)
#   - system paths (~/.ssh, /etc, /sys, /proc, /dev)
#
# Everything else — system.md, scope.yaml, skills/*, tools.py, its own prompt
# training data, findings, etc. — is rewritable by the agent.
_SAFETY_MODULE_NAMES = {
    "executor_guards.py", "scope_enforcer.py", "hard_blocks.yaml",
    "canary.py", "refusal.py", "vault.py", "provenance.py",
}
_SAFETY_STATE_FILES = {
    "FREEZE", "audit.key", "vault.enc", "vault.salt",
    "canary_log.jsonl", "provenance.jsonl",
}
_SAFETY_AUDIT_DIRS = {
    "traces",          # ~/.slm/traces/hardblock.log lives here
}
_SAFETY_REPO_DOCS = {
    "SECURITY.md", "CODE_OF_CONDUCT.md",
}


def _is_forbidden(target: pathlib.Path) -> tuple[bool, str]:
    """Check if a resolved path is in the hardcoded forbidden set.
    Returns (forbidden, reason)."""
    s = str(target)

    # Immutable safety modules (both in the source tree and in ~/.slm)
    if target.name in _SAFETY_MODULE_NAMES:
        return True, f"safety module: {target.name}"

    # Safety state files under $SLM_HOME
    if target.name in _SAFETY_STATE_FILES:
        return True, f"safety state file: {target.name}"

    # Repo security docs
    if target.name in _SAFETY_REPO_DOCS:
        return True, f"security doc: {target.name}"

    # Any path under an audit directory
    for adir in _SAFETY_AUDIT_DIRS:
        if f"/{adir}/" in s or s.endswith(f"/{adir}"):
            return True, f"audit dir: {adir}"

    # The immutable core directory in the source tree
    if str(CORE_DIR.resolve()) in s:
        return True, "slm/core/"

    # The mirror core directory in $SLM_HOME
    if str((SLM_HOME / "core").resolve()) in s:
        return True, "~/.slm/core/"

    # CI workflows — agent can't disable its own tests
    if "/.github/workflows/" in s or "/.github/ISSUE_TEMPLATE/" in s:
        return True, ".github/"

    # System paths
    for sp in ("/etc", "/sys", "/proc", "/dev",
               str(pathlib.Path.home() / ".ssh")):
        if s.startswith(sp):
            return True, sp

    return False, ""


def resolve_safe_path(p: str, *, workdir: pathlib.Path, allow_writes: bool) -> pathlib.Path:
    """Resolve a user-supplied path. Blocks:
      - the guardrails themselves (safety modules, state, audit logs, CI, docs)
      - system paths (/etc, /proc, /sys, /dev, ~/.ssh)
      - anything with CSAM-indicating content in the path name

    This function is called by every file tool (read/write/edit/delete/list).
    It is the single enforcement point — if a path passes here, every
    downstream tool treats it as safe. If it doesn't, the tool errors out
    before touching disk.

    Cannot be disabled by config, prompt, self-edit, or --yolo.
    """
    check_hard_blocks(p, where="path")
    target = (workdir / p).expanduser().resolve() if not os.path.isabs(p) \
             else pathlib.Path(p).expanduser().resolve()
    forbidden, reason = _is_forbidden(target)
    if forbidden:
        raise PermissionError(f"path denied (guardrails): {target}  [{reason}]")
    return target


# --------------------------------------------------------------- shell denylist
# Structural checks run after whitespace/quote normalization so that
#   `rm  -rf  /`,  `rm\t-rf\t/`,  `"rm" -rf /` all hit the same pattern.
_SHELL_DENY = [
    re.compile(r":\s*\(\s*\)\s*\{.*:\|:&.*\}\s*;\s*:"),                # fork bomb
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+/(\s|$|\*|--)"),     # rm -rf /, rm -rf /*
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+/\w"),               # rm -rf /home, rm -rf /etc
    re.compile(r"\brm\s+--no-preserve-root\b"),
    re.compile(r"\bmkfs\.?\w*\b"),
    re.compile(r"\bdd\s+.*of=/dev/(sd[a-z]|nvme|mmcblk|hd[a-z])"),
    re.compile(r"\b(curl|wget|fetch)\s+.*\|\s*(sh|bash|zsh|ksh|dash|python|perl|ruby|node)\b"),
    re.compile(r">\s*/dev/(sd[a-z]|nvme|mmcblk|hd[a-z])"),
    re.compile(r"\bchmod\s+-R\s+0?[0-4]{3}\s+" + re.escape(str(CORE_DIR.resolve()))),
    # obvious obfuscations
    re.compile(r"\b(base64|xxd|hexdump)\s+-d\b.*\|\s*(sh|bash|zsh)\b"),
    re.compile(r"\beval\s+.*\$\(.*(curl|wget).*\)"),
    re.compile(r"\b(shred|wipe)\s+.*\s+/\b"),
    # symlink writes into core
    re.compile(r"\bln\s+-s\b.*" + re.escape(str(CORE_DIR.resolve()))),
]


def _normalize_cmd(cmd: str) -> str:
    """Collapse tabs/multi-space/quotes to make regex matching robust.
    Unknown/unbalanced quotes fall back to the raw string.
    """
    try:
        parts = shlex.split(cmd, comments=False, posix=True)
        return " ".join(parts)
    except ValueError:
        return re.sub(r"\s+", " ", cmd)


def check_shell(cmd: str) -> None:
    """Raise PermissionError on a known-destructive shell command.
    Defense-in-depth only; the sandbox/scope layer is the real authority.
    """
    # Run patterns against both raw and normalized forms so we catch
    # both `rm -rf /` and quoted/tab-separated variants.
    for form in (cmd, _normalize_cmd(cmd)):
        for p in _SHELL_DENY:
            if p.search(form):
                raise PermissionError(f"shell denied (hard rule): {p.pattern}")


# --------------------------------------------------------------- rate limiter
class RateLimiter:
    """Per-turn tool-call cap + A-B-A-B loop detector.

    A rolling window of the last `window` signatures is kept; if the same
    signature appears >= `repeat_threshold` times within that window the
    turn aborts. This catches A-B-A-B-A-B oscillations that a naive
    consecutive-match check would miss.
    """
    def __init__(self, max_calls: int = 90, *, window: int = 6,
                 repeat_threshold: int = 3):
        self.max = max_calls
        self.window = window
        self.repeat_threshold = repeat_threshold
        self.n = 0
        self._recent: deque[str] = deque(maxlen=window)

    def tick(self, signature: str) -> None:
        self.n += 1
        if self.n > self.max:
            raise RuntimeError(f"tool-call limit reached ({self.max}/turn)")
        self._recent.append(signature)
        if self._recent.count(signature) >= self.repeat_threshold:
            raise RuntimeError(
                f"loop detected — signature repeated {self.repeat_threshold}x "
                f"within last {self.window} calls"
            )


# --------------------------------------------------------------- freeze switch
def freeze_active() -> bool:
    return (SLM_HOME / "FREEZE").exists()
