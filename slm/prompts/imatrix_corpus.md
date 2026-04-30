# Imatrix calibration corpus

The imatrix file biases quantization to preserve activations the model actually uses. For a bug-bounty agent we calibrate on security-relevant text rather than generic web so 2-bit weights retain capability where it matters.

## Target size
~200–300 MB of plain text. Concatenate into a single `imatrix_corpus.txt`.

## Sources (all public / permissive)
| Source | What to include | Approx size |
|---|---|---|
| HackerOne hacktivity (public reports) | Raw text of disclosed reports | 40 MB |
| Bugcrowd public disclosures | Same | 20 MB |
| CVE Mitre descriptions (2019–2025) | `nvdcve-*.json` → description field | 30 MB |
| PayloadAllTheThings (full repo) | All .md files concatenated | 25 MB |
| HackTricks (book) | All .md | 25 MB |
| exploit-db snippets (metadata + small POCs) | Skip anything >50 KB | 20 MB |
| OWASP cheatsheets | All .md | 10 MB |
| ctftime writeups (top 500) | Scraped markdown | 30 MB |
| Our own SFT traces | The exact output format we train on | ~20 MB |

## Important
- Strip HTML / boilerplate.
- Keep English-only (the base is multilingual; we want capacity on EN security text).
- Shuffle at file-level before concatenation.
- Do NOT include binaries or base64 blobs — waste of activations.

## Build command
```bash
cat corpus/*.txt | shuf | head -c 250M > imatrix_corpus.txt
```
