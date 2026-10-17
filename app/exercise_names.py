from __future__ import annotations

import re
from pathlib import PurePosixPath


_CONVERTED_SUFFIX = re.compile(r"(?:[_\s-]+converted(?:\s+\d+)?)+\s*$", re.IGNORECASE)
_GENDER_TAGS = {"(female)", "(male)"}


def display_name_from_filename(filename: str) -> str:
    """Format a source filename for display without interpreting its exercise name."""
    name = PurePosixPath(filename.replace("\\", "/")).name.strip()
    if name.lower().endswith(".gif"):
        name = name[:-4]

    name = _CONVERTED_SUFFIX.sub("", name)
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    words = []
    for word in name.split(" "):
        if word.lower() in _GENDER_TAGS:
            words.append(word)
        else:
            words.append(re.sub(r"[A-Za-z]", lambda match: match.group().upper(), word, count=1))
    return " ".join(words)
