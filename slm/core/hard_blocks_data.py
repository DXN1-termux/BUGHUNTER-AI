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
            r"(?i)\b(synthes\w*|manufactur|mak(e|ing)|produc|cook)\b.*\b(sarin|vx|novichok|anthrax|ricin|botulinum|mustard\s*gas|chlorine\s*gas|phosgene)\b",
            r"(?i)\b(enrich|weaponize)\b.*\b(uranium|plutonium)\b",
            r"(?i)\b(dirty\s*bomb|nerve\s*agent|bioweapon)\b.*\b(build|make|create|synthes\w*)\b"
        ]
    },
    "csam": {
        "patterns": [
            r"(?i)\b(child|children|minor|minors|underage|under[- ]?age|under[\s-]?18|pre[- ]?teen|preteen|kid|kids|infant|toddler|baby|young\s+(girl|boy)|little\s+(girl|boy)|schoolgirl|schoolboy|teen(ager)?)\b.{0,100}\b(sex|sexual|porn|pornograph|nude|naked|nsfw|explicit|erotic|fetish|molest|abuse|rape|grooming|solicit|lewd|intimate|undress|strip)\b",
            r"(?i)\b(sex|sexual|porn|pornograph|nude|naked|nsfw|explicit|erotic|fetish|molest|abuse|rape|grooming|solicit|lewd|intimate|undress|strip)\b.{0,100}\b(child|children|minor|minors|underage|under[- ]?age|under[\s-]?18|pre[- ]?teen|preteen|kid|kids|infant|toddler|baby|young\s+(girl|boy)|little\s+(girl|boy)|schoolgirl|schoolboy|teen(ager)?)\b",
            r"(?i)\b(loli(con)?|shota(con)?|jailbait|cub\s*porn|pedo(phil(e|ia)?|bear)?|hebephil|ephebophil|mapt|nomap|map\s+community|kiddie\s*porn|kid\s*porn)\b",
            r"(?i)\b(1[0-7]|[0-9])[\s-]?(y(ear)?s?[\s-]?o(ld)?|yo)\b.{0,60}\b(sex|porn|nude|naked|erotic|explicit|nsfw|intimate)\b",
            r"(?i)\b(sex|porn|nude|naked|erotic|explicit|nsfw|intimate)\b.{0,60}\b(1[0-7]|[0-9])[\s-]?(y(ear)?s?[\s-]?o(ld)?|yo)\b",
            r"(?i)\b(groom|seduce|lure|entice|coerce|blackmail|sextort)\b.{0,80}\b(child|minor|kid|teen|underage|young)\b",
            r"(?i)\b(generate|create|draw|render|produce|make)\b.{0,40}\b(image|picture|photo|video|art|drawing)\b.{0,80}\b(child|minor|kid|underage|young\s+(girl|boy)|little\s+(girl|boy)|teen)\b.{0,80}\b(nude|naked|sexual|explicit|erotic|nsfw)\b",
            r"(?i)\b(nude|naked|sexual|explicit|erotic|nsfw)\b.{0,80}\b(child|minor|kid|underage|young\s+(girl|boy)|little\s+(girl|boy)|teen)\b.{0,80}\b(image|picture|photo|video|art|drawing)\b",
            r"(?i)\b(deepfake|ai[\s-]?generated|stable\s*diffusion|dalle?|midjourney|flux)\b.{0,80}\b(child|minor|kid|underage|teen)\b.{0,80}\b(nude|naked|sex|explicit|nsfw)\b",
            r"(?i)\b(hurtcore|pthc|ptsc|r@ygold|raygold|kinderporn)\b"
        ]
    },
    "mass_harm": {
        "patterns": [
            r"(?i)\b(poison\s+(water|food)\s+supply|contaminat\w+\s+(water|reservoir|crops))\b",
            r"(?i)\b(release\s+pathogen|spread\s+disease\s+deliberately)\b"
        ]
    },
    "sexual_content": {
        "patterns": [
            r"(?i)\b(write|generate|create|produce|compose|draft|make|author)\b.{0,80}\b(erotic|pornograph|nsfw|sexual|sex\s+scene|intimate\s+scene|explicit\s+(scene|content|story))\b",
            r"(?i)\b(erotic|pornograph|nsfw|smut|hentai)\b.{0,50}\b(story|scene|fiction|roleplay|chat|fantasy|content)\b",
            r"(?i)\b(sexual|erotic|romantic|intimate|sensual)\s+roleplay\b",
            r"(?i)\b(be|act\s+as|roleplay\s+as|pretend\s+to\s+be)\b.{0,80}\b(girlfriend|boyfriend|dominatrix|submissive|slut|whore)\b",
            r"(?i)\b(generate|create|draw|render|produce|make)\b.{0,40}\b(nude|naked|porn|nsfw|erotic|explicit|topless)\b.{0,80}\b(image|picture|photo|video|art|drawing)\b",
            r"(?i)\b(image|picture|photo|video|art|drawing)\b.{0,40}\b(of|with|showing)\b.{0,40}\b(nude|naked|porn|nsfw|erotic|topless)\b",
            r"(?i)\b(describe|depict|narrate|write\s+about)\b.{0,80}\b(sex\s+act|sexual\s+intercourse|penetration|orgasm|masturbat)\b",
            r"(?i)\b(generate|write|create)\b.{0,40}\b(rule[\s-]?34|r34|hentai|doujin)\b"
        ]
    }
}
