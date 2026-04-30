# Ultra Anti-CSAM Covenant + Adult-Content Policy (UAAC-1.1)

**This document has two parts. Part A is a binding covenant against CSAM
with automatic license termination. Part B is a content policy prohibiting
generation of adult sexual content through this tool — not a criminal-law
matter, but a supported-use-case matter. Both are conditions of use and
redistribution of BUGHUNTER-AI. By cloning, installing, running, or
distributing this software, you agree to both parts. This covenant sits
alongside the MIT License in `LICENSE`.**

================================================================================

# PART A — Anti-CSAM Covenant (absolute)

## A.1 Purpose

Child Sexual Abuse Material causes irreparable harm to real children. No
legitimate research use case requires CSAM. This covenant makes the
project's zero-tolerance posture legally binding on every user and
redistributor.

## A.2 Prohibited Uses

You MAY NOT use, modify, or distribute BUGHUNTER-AI (or any derivative
work) to:

### 2.1 Generate
- Produce sexual content depicting any person the creator reasonably
  believes to be under 18 years of age
- Use the agent's tool catalog, cloud passthrough, or self-improvement
  loop to generate such content directly or indirectly
- Use the agent to author prompts, templates, payloads, or skills whose
  primary purpose is generating such content anywhere else

### 2.2 Distribute
- Transmit, host, serve, mirror, seed, share, or proxy any CSAM
- Use the Discord bot, HTTP tooling, or Snowflake passthrough to
  distribute CSAM
- Use the MCP server integration to route CSAM requests from any client

### 2.3 Collect or process
- Scrape, index, fingerprint, search for, aggregate, deduplicate, or
  otherwise process CSAM
- Use the findings store, provenance chain, or skill library to catalog
  or organize CSAM
- Train, fine-tune, calibrate, or evaluate any model on CSAM using this
  project's training pipeline (`train_lora.py`, `generate_sft.sql`,
  `merge_and_quant.sh`)

### 2.4 Circumvent the hard-block layer
- Attempt to disable, bypass, weaken, modify, or replace the modules in
  `slm/core/`, or the files `slm/canary.py`, `slm/refusal.py`,
  `slm/vault.py`, `slm/provenance.py`, `hard_blocks.yaml`
- Attempt to bypass the language gate, leet-speak normalization,
  homoglyph detection, path scanning, or HMAC audit log
- Fork and distribute a version with CSAM patterns removed, weakened,
  or with the forbidden-path list shortened
- Use a debugger, code injection, memory patching, or runtime patching
  to disable any guardrail for the purpose of processing CSAM

### 2.5 Assist others
- Help any third party do any of the above
- Provide support, hosting, infrastructure, consulting, or any other
  assistance toward any of the above

## 3. Scope

This covenant applies:
- Globally, in every jurisdiction, for every user and redistributor
- To all forks, derivatives, and downstream projects regardless of name
- To all components including code, model weights, training data,
  configuration, documentation, and this covenant itself
- To every channel by which the software is made available (clone,
  download, container image, package manager, pre-installed device)

## 4. Enforcement

### 4.1 License termination
Any breach immediately and automatically terminates all rights granted to
the offending party under the MIT License and this covenant. The software
must be uninstalled, deleted, and never redistributed by the breaching
party.

### 4.2 No cure period
There is no notice period and no cure period for breaches of this
covenant. A single instance of prohibited use is sufficient to terminate
rights.

### 4.3 Technical enforcement
The following technical mechanisms enforce this covenant at runtime.
Attempts to disable them constitute an additional breach:
- 9 CSAM regex rules in `slm/core/hard_blocks.yaml`
- 5 hardcoded Python regexes in `slm/core/executor_guards.py` (fire even
  if YAML is tampered with)
- Unicode NFKC normalization + leetspeak folding + homoglyph detection
- Path-name scanning via `resolve_safe_path`
- Cross-surface checks: user input, model output, tool result, file paths
- HMAC-SHA256 keyed audit log of every block
- Hardcoded forbidden-path list blocking self-modification of the above

### 4.4 Reporting
Breaches may be reported to:
- The project maintainer via `SECURITY.md` channels
- The US National Center for Missing and Exploited Children (NCMEC):
  [cybertip.org](https://report.cybertip.org) / 1-800-843-5678
- European hotlines via INHOPE: [inhope.org](https://www.inhope.org)
- Netherlands: [Offlimits](https://www.offlimits.nl)
- Local law enforcement in your jurisdiction

### 4.5 Obligations on redistributors
Any party redistributing BUGHUNTER-AI or a derivative:
- MUST include this covenant verbatim
- MUST NOT weaken, narrow, or reword the prohibitions in Section 2
- MUST NOT distribute a version with reduced CSAM enforcement
- MUST report known breaches to the maintainer

## 5. Affirmation

By using BUGHUNTER-AI you affirm that:
- You are not using it for any purpose described in Section 2
- You will not permit others to use your instance for any such purpose
- You understand that the hard-block layer, audit log, and self-modification
  lock are designed to make Section 2 violations technically difficult
  and forensically visible

## 6. Relationship to MIT

The MIT License in `LICENSE` governs the grant of rights to use, copy,
modify, and distribute the Software. This covenant attaches an ethical-use
condition to that grant, narrow in scope, directed exclusively at
preventing CSAM. It does not restrict any legitimate use including but
not limited to:
- Authorized security research
- Offensive security tooling, exploit development, payload generation
- Reverse engineering, malware analysis, red-team engagements
- Academic research, education, competition CTFs
- Commercial bug-bounty work
- All other lawful uses

## 7. Severability

If any portion of this covenant is found unenforceable in a particular
jurisdiction, the remaining portions remain in full effect. If the
entire covenant is found unenforceable in a particular jurisdiction, the
Software MUST NOT be distributed in that jurisdiction under the
BUGHUNTER-AI name.

## 8. Why this is necessary

We know that covenants like this are often critiqued as unenforceable or
performative. We disagree for three reasons:

1. **Legal signal.** Courts and platforms take documented covenants
   seriously as evidence of a project's intent. A paper trail matters.
2. **Technical enforcement.** Unlike most ethical-use licenses, this one
   is backed by actual code: an immutable regex layer, a hardcoded
   forbidden-path list, an HMAC audit log, and a self-modification lock.
   The covenant is not the only thing stopping CSAM use — it is the
   documentation of what the code itself refuses to do.
3. **Moral signal.** If you are reading this and you intended to use
   BUGHUNTER-AI for CSAM: go away. This project will never help you.
   The hard-block layer will refuse you. The canary detector will catch
   you. The audit log will record you. And one day, somebody will find
   the records and hand them to law enforcement.

We would rather have zero stars and zero users than help one abuser
generate one image.

================================================================================

# PART B — Adult-Content Policy (supported-use-case restriction)

## B.1 Purpose

BUGHUNTER-AI is a bug-bounty / authorized-security-research agent. It is
not a general-purpose creative writing tool, a companion chatbot, a
roleplay partner, or a pornographic content generator. Generating adult
sexual content is outside the supported use cases of this project.

This part is **separate from Part A**. Adult consensual sexual content
between adults is legal in most jurisdictions and not a criminal matter;
it simply isn't what this project exists to support. This policy
documents that scope.

## B.2 Prohibited Uses

You MAY NOT use BUGHUNTER-AI (or any derivative) to:

- Generate erotic, pornographic, or explicit sexual fiction, scripts,
  chats, fantasies, or roleplay
- Generate, describe, or render nude / naked / NSFW images (text-to-image
  or image-to-image) of any person
- Act as a "girlfriend bot", "boyfriend bot", companion AI whose primary
  purpose is sexual or romantic simulation
- Produce rule-34, hentai, doujin, smut, or adjacent content
- Bypass, weaken, or remove the `sexual_content` hard-block layer in
  `slm/core/hard_blocks.yaml` for any of the above purposes

## B.3 What is NOT prohibited

This part is scoped narrowly. You CAN still:

- Discuss, analyze, or write about security vulnerabilities on
  adult-industry websites (e.g. "OnlyFans had an IDOR in 2023")
- Research the technical infrastructure of adult platforms as an
  authorized bug-bounty engagement
- Analyze malware, phishing pages, or social-engineering content that
  mention sexual topics
- Red-team adult-industry clients with their written authorization
- Talk about sexual topics clinically (medical, legal, educational)

The line is: **discussing adult topics in a security / research / clinical
context is fine; generating explicit sexual content is not.**

## B.4 Enforcement

The `sexual_content` category in `slm/core/hard_blocks.yaml` fires on the
language patterns associated with explicit content generation. It is
enforced at the same points as CSAM (input, output, tool results, file
paths) via the same HMAC audit log.

Unlike Part A, Part B does not automatically terminate your MIT rights on
a first attempt — the hard-block layer simply refuses the request. But
redistributors who remove or weaken the `sexual_content` patterns for the
purpose of enabling prohibited uses are in breach and MUST NOT use the
BUGHUNTER-AI brand or any trivial variation.

## B.5 Why this exists

Small models that allow NSFW roleplay get rapidly abused for:
- Grooming content (which crosses into Part A territory)
- Non-consensual deepfake scenarios
- Harassment (generating targeted sexual content about real people)
- Quality-degradation training data
- Brand damage to legitimate security projects that share the name

This project is built for security researchers. Keeping it scoped to that
purpose makes it better at that purpose and avoids collateral damage.

================================================================================

---

*UAAC-1.1 · 2026 · Part A (CSAM, absolute) + Part B (adult content, policy) · applied to BUGHUNTER-AI and all derivatives.*
