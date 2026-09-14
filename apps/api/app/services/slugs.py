"""URL slugs that survive German boat names.

Stripping umlauts to a dash turns "Fördeperle" into "f-rdeperle"; transliterating keeps the
name readable in the URL and keeps the slug stable when the same name is seeded again.
"""

import re
import unicodedata

TRANSLITERATION = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "ae",
        "Ö": "oe",
        "Ü": "ue",
        "å": "aa",
        "æ": "ae",
        "ø": "oe",
        "Å": "aa",
        "Æ": "ae",
        "Ø": "oe",
    }
)


def slugify(value: str, fallback: str = "eintrag") -> str:
    text = (value or "").translate(TRANSLITERATION)
    # Decompose the rest (é -> e) and drop what is left of the accents.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or fallback


def unique_slug(base: str, exists: "callable[[str], bool]", fallback: str = "eintrag") -> str:
    """Appends -2, -3, ... until `exists` says the slug is free."""
    root = slugify(base, fallback)
    candidate, counter = root, 1
    while exists(candidate):
        counter += 1
        candidate = f"{root}-{counter}"
    return candidate
