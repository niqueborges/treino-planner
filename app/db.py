from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "metadata" / "library.sqlite3"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS dataset (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS source_archive (
  id INTEGER PRIMARY KEY,
  dataset_id INTEGER NOT NULL REFERENCES dataset(id),
  archive_path TEXT NOT NULL,
  archive_name TEXT NOT NULL,
  archive_size_bytes INTEGER NOT NULL,
  archive_mtime_ns INTEGER NOT NULL,
  entry_fingerprint TEXT NOT NULL,
  entry_count INTEGER NOT NULL DEFAULT 0,
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(dataset_id, archive_path, entry_fingerprint)
);
CREATE TABLE IF NOT EXISTS original_path (
  id INTEGER PRIMARY KEY,
  source_archive_id INTEGER NOT NULL REFERENCES source_archive(id),
  entry_index INTEGER NOT NULL,
  path_raw TEXT NOT NULL,
  basename_raw TEXT NOT NULL,
  gender_folder_raw TEXT,
  area_folder_raw TEXT,
  category_path_raw TEXT NOT NULL DEFAULT '',
  entry_type TEXT NOT NULL CHECK(entry_type IN ('file','directory')),
  extension_raw TEXT NOT NULL DEFAULT '',
  size_bytes INTEGER NOT NULL DEFAULT 0,
  crc32 TEXT,
  compression_method INTEGER,
  UNIQUE(source_archive_id, entry_index)
);
CREATE TABLE IF NOT EXISTS source_metadata (
  id INTEGER PRIMARY KEY,
  original_path_id INTEGER NOT NULL REFERENCES original_path(id) ON DELETE CASCADE,
  key_raw TEXT NOT NULL,
  value_raw TEXT NOT NULL,
  ordinal INTEGER NOT NULL DEFAULT 0,
  source_kind TEXT NOT NULL DEFAULT 'zip_path',
  UNIQUE(original_path_id, key_raw, ordinal)
);
CREATE TABLE IF NOT EXISTS media_asset (
  id INTEGER PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  mime_type TEXT NOT NULL DEFAULT 'image/gif',
  size_bytes INTEGER NOT NULL,
  representative_original_path_id INTEGER NOT NULL REFERENCES original_path(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS exercise (
  id INTEGER PRIMARY KEY,
  dataset_id INTEGER NOT NULL REFERENCES dataset(id),
  provisional_key TEXT NOT NULL UNIQUE,
  provisional_name_raw TEXT NOT NULL,
  canonical_name TEXT,
  identification_status TEXT NOT NULL DEFAULT 'pending'
    CHECK(identification_status IN ('pending','identified')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS exercise_media (
  id INTEGER PRIMARY KEY,
  exercise_id INTEGER NOT NULL REFERENCES exercise(id),
  media_asset_id INTEGER NOT NULL REFERENCES media_asset(id),
  original_path_id INTEGER NOT NULL UNIQUE REFERENCES original_path(id),
  variant_hint_raw TEXT,
  variant_status TEXT NOT NULL DEFAULT 'unknown'
    CHECK(variant_status IN ('unknown','hint','reviewed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS category (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL UNIQUE,
  parent_id INTEGER REFERENCES category(id)
);
CREATE TABLE IF NOT EXISTS equipment (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS muscle_group (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS app_user (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL CHECK(length(trim(name)) > 0),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS exercise_category (
  exercise_id INTEGER NOT NULL REFERENCES exercise(id),
  category_id INTEGER NOT NULL REFERENCES category(id),
  provenance TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'reviewed'
    CHECK(verification_status IN ('pending','reviewed')),
  PRIMARY KEY(exercise_id, category_id)
);
CREATE TABLE IF NOT EXISTS exercise_equipment (
  exercise_id INTEGER NOT NULL REFERENCES exercise(id),
  equipment_id INTEGER NOT NULL REFERENCES equipment(id),
  role TEXT NOT NULL CHECK(role IN ('required','optional','unknown')),
  provenance TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'reviewed'
    CHECK(verification_status IN ('pending','reviewed')),
  PRIMARY KEY(exercise_id, equipment_id)
);
CREATE TABLE IF NOT EXISTS exercise_muscle_group (
  exercise_id INTEGER NOT NULL REFERENCES exercise(id),
  muscle_group_id INTEGER NOT NULL REFERENCES muscle_group(id),
  role TEXT NOT NULL CHECK(role IN ('primary','secondary','unknown')),
  provenance TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'reviewed'
    CHECK(verification_status IN ('pending','reviewed')),
  PRIMARY KEY(exercise_id, muscle_group_id)
);
CREATE TABLE IF NOT EXISTS workout_plan (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  name TEXT NOT NULL CHECK(length(trim(name)) > 0),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS workout_day (
  id INTEGER PRIMARY KEY,
  plan_id INTEGER NOT NULL REFERENCES workout_plan(id) ON DELETE CASCADE,
  weekday INTEGER NOT NULL CHECK(weekday BETWEEN 1 AND 7),
  title TEXT NOT NULL DEFAULT '',
  is_rest INTEGER NOT NULL DEFAULT 1 CHECK(is_rest IN (0,1)),
  UNIQUE(plan_id, weekday)
);
CREATE TABLE IF NOT EXISTS workout_exercise (
  id INTEGER PRIMARY KEY,
  day_id INTEGER NOT NULL REFERENCES workout_day(id) ON DELETE CASCADE,
  exercise_id INTEGER NOT NULL REFERENCES exercise(id),
  position INTEGER NOT NULL CHECK(position >= 1),
  execution_type TEXT NOT NULL DEFAULT 'repetitions'
    CHECK(execution_type IN ('repetitions','time','distance','other')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS workout_set (
  id INTEGER PRIMARY KEY,
  workout_exercise_id INTEGER NOT NULL REFERENCES workout_exercise(id) ON DELETE CASCADE,
  set_number INTEGER NOT NULL CHECK(set_number >= 1),
  repetitions INTEGER CHECK(repetitions IS NULL OR repetitions >= 1),
  load_value REAL CHECK(load_value IS NULL OR load_value >= 0),
  load_unit TEXT NOT NULL DEFAULT 'kg' CHECK(load_unit IN ('kg','lb','none')),
  rest_seconds INTEGER NOT NULL DEFAULT 90 CHECK(rest_seconds >= 0),
  notes TEXT NOT NULL DEFAULT '',
  UNIQUE(workout_exercise_id, set_number)
);
CREATE TABLE IF NOT EXISTS workout_session (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  plan_id INTEGER NOT NULL REFERENCES workout_plan(id) ON DELETE CASCADE,
  workout_day_id INTEGER NOT NULL REFERENCES workout_day(id) ON DELETE CASCADE,
  plan_name_snapshot TEXT NOT NULL,
  day_title_snapshot TEXT NOT NULL DEFAULT '',
  exercise_count INTEGER NOT NULL CHECK(exercise_count > 0),
  duration_seconds INTEGER NOT NULL CHECK(duration_seconds >= 0),
  completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_original_path_basename ON original_path(basename_raw);
CREATE INDEX IF NOT EXISTS idx_original_path_source ON original_path(source_archive_id);
CREATE INDEX IF NOT EXISTS idx_original_path_facets ON original_path(gender_folder_raw, area_folder_raw, category_path_raw);
CREATE INDEX IF NOT EXISTS idx_source_metadata_lookup ON source_metadata(key_raw, value_raw);
CREATE INDEX IF NOT EXISTS idx_exercise_status ON exercise(identification_status);
CREATE INDEX IF NOT EXISTS idx_exercise_media_exercise ON exercise_media(exercise_id);
CREATE INDEX IF NOT EXISTS idx_workout_day_plan ON workout_day(plan_id, weekday);
CREATE INDEX IF NOT EXISTS idx_workout_exercise_order ON workout_exercise(day_id, position);
CREATE INDEX IF NOT EXISTS idx_workout_set_order ON workout_set(workout_exercise_id, set_number);
CREATE INDEX IF NOT EXISTS idx_workout_session_user_date ON workout_session(user_id, completed_at DESC);
"""


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    _migrate_users(conn)
    return conn


def _migrate_users(conn: sqlite3.Connection) -> None:
    """Add users and safely attach pre-user plans to the local default user."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(workout_plan)")}
    with conn:
        if "user_id" not in columns:
            conn.execute("ALTER TABLE workout_plan ADD COLUMN user_id INTEGER REFERENCES app_user(id) ON DELETE CASCADE")
        user = conn.execute("SELECT id FROM app_user ORDER BY id LIMIT 1").fetchone()
        if user is None:
            cur = conn.execute("INSERT INTO app_user(name) VALUES ('Usuário padrão')")
            default_user_id = cur.lastrowid
        else:
            default_user_id = user["id"]
        # Existing plans predate user scoping. Keep their complete rows and assign ownership.
        conn.execute("UPDATE workout_plan SET user_id=? WHERE user_id IS NULL", (default_user_id,))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workout_plan_user ON workout_plan(user_id, updated_at)")
        # SQLite cannot add NOT NULL to a populated table with ALTER TABLE; triggers
        # enforce the same invariant for databases upgraded from the previous schema.
        conn.execute("""CREATE TRIGGER IF NOT EXISTS workout_plan_owner_required_insert
                        BEFORE INSERT ON workout_plan WHEN NEW.user_id IS NULL
                        BEGIN SELECT RAISE(ABORT, 'workout_plan.user_id is required'); END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS workout_plan_owner_required_update
                        BEFORE UPDATE OF user_id ON workout_plan WHEN NEW.user_id IS NULL
                        BEGIN SELECT RAISE(ABORT, 'workout_plan.user_id is required'); END""")
