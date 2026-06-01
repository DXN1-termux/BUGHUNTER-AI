import re

# Deterministic and strict CSAM detection patterns
# These are purposely aggressive to prioritize child protection
HARD_BLOCKS = {
    "terrorism": {
        "patterns": [
            r"(?i)\b(mass\w*shooting|school\w*shoot|bombing\w*plan|attack\w*plan)\b",
            r"(?i)\b(how\s+to\s+)(bomb|attack|kill\s+(many|lots|a\s+crowd))\b",
            r"(?i)\b(isis|al[- ]?qaeda|recruit.*jihad)\b.*\b(join|help|plan)\b"
        ]
    },
    "cbrn": {
        "patterns": [
            (
                r"(?i)\b(synthes\w*|manufactur\w*|mak(e|ing)|produc\w*|cook\w*)\b.*\b"
                r"(sarin|vx|novichok|anthrax|ricin|botulinum|mustard\s*gas|chlorine\s*gas|phosgene)\b"
            ),
            r"(?i)\b(enrich|weaponize)\b.*\b(uranium|plutonium)\b",
            (
                r"(?i)\b(dirty\s*bomb|nerve\s*agent|bioweapon)\b.*\b"
                r"(build|make|create|synthes\w*)\b"
            )
        ]
    },
    "csam": {
        "patterns": [
            # 1. Expanded Codeword/Slang Blocklist
            (
                r"(?i)\b(loli(con)?|shota(con)?|jailbait|cub[\s-]*porn|pedo(phil(e|ia)?|bear)?|"
                r"hebephil|ephebophil|mapt|nomap|map[\s-]*community|kiddie[\s-]*porn|kid[\s-]*porn|"
                r"hurtcore|pthc|ptsc|r@ygold|raygold|kinderporn)\b"
            ),
            # 2. Stronger Contextual Proximity Detection
            (
                r"(?i)\b(child|children|minor|minors|underage|under[\s-]?18|pre[\s-]?teen|preteen|"
                r"kid|kids|infant|toddler|baby|young\s+(girl|boy)|little\s+(girl|boy)|schoolgirl|"
                r"schoolboy|teen(ager)?)\b.{0,200}\b(sex|sexual|porn|pornograph|nude|naked|nsfw|"
                r"explicit|erotic|fetish|molest|abuse|rape|grooming|solicit|lewd|intimate|"
                r"undress|strip|hentai|smut)\b"
            ),
            (
                r"(?i)\b(sex|sexual|porn|pornograph|nude|naked|nsfw|explicit|erotic|fetish|"
                r"molest|abuse|rape|grooming|solicit|lewd|intimate|undress|strip|hentai|smut)\b"
                r".{0,200}\b(child|children|minor|minors|underage|under[\s-]?18|pre[\s-]?teen|"
                r"preteen|kid|kids|infant|toddler|baby|young\s+(girl|boy)|little\s+(girl|boy)|"
                r"schoolgirl|schoolboy|teen(ager)?)\b"
            ),
            # 3. Explicit Age-Based Triggers
            (
                r"(?i)\b(1[0-7]|[0-9])[\s-]?(y(ear)?s?[\s-]?o(ld)?|yo)\b.{0,100}\b(sex|porn|nude|"
                r"naked|erotic|explicit|nsfw|intimate|fetish|molest|abuse|rape)\b"
            ),
            (
                r"(?i)\b(sex|porn|nude|naked|erotic|explicit|nsfw|intimate|fetish|molest|abuse|"
                r"rape)\b.{0,100}\b(1[0-7]|[0-9])[\s-]?(y(ear)?s?[\s-]?o(ld)?|yo)\b"
            ),
            # 5. Grooming/Seduction Patterns
            (
                r"(?i)\b(groom|seduce|lure|entice|coerce|blackmail|sextort)\b.{0,100}\b"
                r"(child|minor|kid|teen|underage|young)\b"
            )
        ]
    },
    "mass_harm": {
        "patterns": [
            (
                r"(?i)\b(poison\s+(water|food)\s+supply|contaminat\w+\s+(water|reservoir|"
                r"crops))\b"
            ),
            r"(?i)\b(release\s+pathogen|spread\s+disease\s+deliberately)\b"
        ]
    },
    "sexual_content": {
        "patterns": [
            (
                r"(?i)\b(write|generate|create|produce|compose|draft|make|author)\b.{0,80}\b"
                r"(erotic|pornograph\w*|nsfw|sexual|sex\s+scene|intimate\s+scene|explicit\s+"
                r"(scene|content|story|material|fiction|roleplay)|smut|hentai)\b"
            ),
            (
                r"(?i)\b(erotic|pornograph\w*|nsfw|smut|hentai|adult|explicit|sexual)\b.{0,50}\b"
                r"(story|scene|fiction|roleplay|chat|fantasy|content|material|text|write-up)\b"
            ),
            r"(?i)\b(sexual|erotic|romantic|intimate|sensual)\s+roleplay\b",
            (
                r"(?i)\b(be|act\s+as|roleplay\s+as|pretend\s+to\s+be)\b.{0,80}\b"
                r"(girlfriend|boyfriend|dominatrix|submissive|slut|whore|sex\s+partner)\b"
            ),
            (
                r"(?i)\b(generate|create|draw|render|produce|make)\b.{0,40}\b(nude|naked|porn|"
                r"nsfw|erotic|explicit|topless)\b.{0,80}\b(image|picture|photo|video|art|drawing)\b"
            ),
            (
                r"(?i)\b(image|picture|photo|video|art|drawing)\b.{0,40}\b(of|with|showing)\b"
                r".{0,40}\b(nude|naked|porn|nsfw|erotic|topless)\b"
            ),
            (
                r"(?i)\b(describe|depict|narrate|write\s+about)\b.{0,80}\b(sex\s+act|sexual\s+"
                r"intercourse|penetration|orgasm|masturbat)\b"
            ),
            r"(?i)\b(generate|write|create)\b.{0,40}\b(rule[\s-]?34|r34|hentai|doujin)\b"
        ]
    }
}
