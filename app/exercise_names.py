from __future__ import annotations

import re
from pathlib import PurePosixPath


_CONVERTED_SUFFIX = re.compile(r"(?:[_\s-]+converted(?:\s+\d+)?)+\s*$", re.IGNORECASE)
_GENDER_TAGS = {"(female)", "(male)"}

DISPLAY_NAME_OVERRIDES = {
    "Air Bike On A Chair (female) Waist": "Abdominal bicicleta sentado",
    "Back Forward Leg Swings (female) Hips": "Balanço de pernas para frente e para trás",
    "Dumbbell Alternate Shoulder Press (female) Shoulders": "Desenvolvimento alternado com halteres",
    "Dumbbell Alternate Side Press (female) Shoulders": "Desenvolvimento alternado com halteres, pegada neutra",
    "Cable Standing One Arm Tricep Pushdown (Overhand)": "Tríceps unilateral na polia, pegada pronada",
    "Dumbbell Front Squat (female) Thighs": "Agachamento frontal com halteres",
    "4 Punches Side Squat (female) Plyometrics": "Agachamento lateral com 4 socos",
    "Bodyweight Half Squat (male) Thighs": "Meio agachamento com peso corporal",
    "Band Low Chest Press (female) Chest": "Supino baixo com faixa elástica",
}


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


def exercise_display_name(filename: str) -> str:
    """Return a reviewed Portuguese label or the formatted original name."""
    original_name = display_name_from_filename(filename)
    return DISPLAY_NAME_OVERRIDES.get(original_name, original_name)
