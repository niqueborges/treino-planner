from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
import zipfile
from pathlib import Path
from typing import Callable, Iterable

from .db import connect

DATASET_NAME = "GIFS PLANEJADOR - ORGANIZADOS"
CHUNK_SIZE = 1024 * 1024


def _entry_fingerprint(entries: list[zipfile.ZipInfo]) -> str:
    h = hashlib.sha256()
    for entry in entries:
        row = (entry.filename, entry.is_dir(), entry.file_size, entry.CRC,
               entry.compress_type, entry.flag_bits)
        h.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _sha256_zip_entry(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(entry, "r") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _segments(path: str) -> list[str]:
    return [part for part in path.replace("\\", "/").split("/") if part]


def _upsert_path_segments(conn: sqlite3.Connection, path_id: int, path_raw: str) -> None:
    for ordinal, segment in enumerate(_segments(path_raw)):
        conn.execute(
            "INSERT OR IGNORE INTO source_metadata(original_path_id,key_raw,value_raw,ordinal,source_kind) "
            "VALUES(?,?,?,?, 'zip_path_segment')",
            (path_id, f"path_segment_{ordinal}", segment, ordinal),
        )


def _add_path(conn: sqlite3.Connection, archive_id: int, entry_index: int,
              entry: zipfile.ZipInfo) -> tuple[int, bool]:
    entry_type = "directory" if entry.is_dir() else "file"
    raw_path = entry.filename
    basename = _segments(raw_path)[-1] if _segments(raw_path) else raw_path
    segments = _segments(raw_path)
    directory_segments = segments if entry.is_dir() else segments[:-1]
    gender_raw = directory_segments[1] if len(directory_segments) > 1 else None
    area_raw = directory_segments[2] if len(directory_segments) > 2 else None
    category_path_raw = "/".join(directory_segments[3:]) if len(directory_segments) > 3 else ""
    suffix = Path(basename).suffix.lower()
    conn.execute(
        "INSERT OR IGNORE INTO original_path "
        "(source_archive_id,entry_index,path_raw,basename_raw,gender_folder_raw,area_folder_raw,category_path_raw,"
        "entry_type,extension_raw,size_bytes,crc32,compression_method) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (archive_id, entry_index, raw_path, basename, gender_raw, area_raw, category_path_raw,
         entry_type, suffix, entry.file_size,
         f"{entry.CRC:08x}" if not entry.is_dir() else None,
         entry.compress_type if not entry.is_dir() else None),
    )
    inserted = conn.execute("SELECT changes()").fetchone()[0] == 1
    row = conn.execute(
        "SELECT id FROM original_path WHERE source_archive_id=? AND entry_index=?",
        (archive_id, entry_index),
    ).fetchone()
    assert row is not None
    _upsert_path_segments(conn, int(row["id"]), raw_path)
    return int(row["id"]), inserted


def _import_one(conn: sqlite3.Connection, archive_path: Path, dataset_id: int) -> dict[str, int | str | bool]:
    stat = archive_path.stat()
    with zipfile.ZipFile(archive_path) as zf:
        entries = zf.infolist()
        fingerprint = _entry_fingerprint(entries)
        archive_path_raw = str(archive_path.resolve())
        existing_archive = conn.execute(
            "SELECT id FROM source_archive WHERE dataset_id=? AND archive_path=? AND entry_fingerprint=?",
            (dataset_id, archive_path_raw, fingerprint),
        ).fetchone()
        if existing_archive:
            return {"archive": archive_path.name, "skipped": True, "gif_occurrences": 0, "new_media": 0, "new_paths": 0}

        conn.execute("BEGIN")
        cur = conn.execute(
            "INSERT INTO source_archive "
            "(dataset_id,archive_path,archive_name,archive_size_bytes,archive_mtime_ns,entry_fingerprint,entry_count) "
            "VALUES(?,?,?,?,?,?,?)",
            (dataset_id, archive_path_raw, archive_path.name, stat.st_size,
             stat.st_mtime_ns, fingerprint, len(entries)),
        )
        archive_id = int(cur.lastrowid)
        gif_occurrences = new_media = new_paths = 0
        for entry_index, entry in enumerate(entries):
            occurrence_id, inserted_path = _add_path(conn, archive_id, entry_index, entry)
            new_paths += int(inserted_path)
            if entry.is_dir() or Path(entry.filename).suffix.lower() != ".gif":
                continue

            sha = _sha256_zip_entry(zf, entry)
            media = conn.execute("SELECT id FROM media_asset WHERE sha256=?", (sha,)).fetchone()
            if media is None:
                mime = mimetypes.guess_type(entry.filename)[0] or "image/gif"
                cur = conn.execute(
                    "INSERT INTO media_asset(sha256,mime_type,size_bytes,representative_original_path_id) "
                    "VALUES(?,?,?,?)", (sha, mime, entry.file_size, occurrence_id),
                )
                media_id = int(cur.lastrowid)
                new_media += 1
            else:
                media_id = int(media["id"])

            provisional_key = hashlib.sha256(
                f"{archive_id}\0{entry_index}".encode("utf-8")
            ).hexdigest()
            exercise = conn.execute(
                "SELECT id FROM exercise WHERE provisional_key=?", (provisional_key,)
            ).fetchone()
            if exercise is None:
                cur = conn.execute(
                    "INSERT INTO exercise(dataset_id,provisional_key,provisional_name_raw,identification_status) "
                    "VALUES(?,?,?,'pending')",
                    (dataset_id, provisional_key, Path(entry.filename).name),
                )
                exercise_id = int(cur.lastrowid)
            else:
                exercise_id = int(exercise["id"])
            conn.execute(
                "INSERT OR IGNORE INTO exercise_media "
                "(exercise_id,media_asset_id,original_path_id,variant_status) VALUES(?,?,?,'unknown')",
                (exercise_id, media_id, occurrence_id),
            )
            gif_occurrences += 1
        conn.commit()
    return {"archive": archive_path.name, "skipped": False, "gif_occurrences": gif_occurrences,
            "new_media": new_media, "new_paths": new_paths}


def expand_archives(inputs: Iterable[str | Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        path = Path(item).expanduser()
        if path.is_dir():
            paths.extend(sorted(p for p in path.rglob("*.zip") if p.is_file()))
        elif path.is_file() and path.suffix.lower() == ".zip":
            paths.append(path)
        else:
            raise FileNotFoundError(f"ZIP or directory not found: {path}")
    unique = {str(p.resolve()): p.resolve() for p in paths}
    return sorted(unique.values(), key=lambda p: str(p).casefold())


def import_dataset(inputs: Iterable[str | Path], db_path: str | Path,
                   progress: Callable[[dict[str, int | str | bool]], None] | None = None
                   ) -> list[dict[str, int | str | bool]]:
    archives = expand_archives(inputs)
    if not archives:
        raise ValueError("No ZIP archives found.")
    results = []
    conn = connect(db_path)
    try:
        conn.execute("INSERT OR IGNORE INTO dataset(name,notes) VALUES(?,?)",
                     (DATASET_NAME, "Imported from ZIP files; original paths preserved."))
        dataset_id = int(conn.execute("SELECT id FROM dataset WHERE name=?", (DATASET_NAME,)).fetchone()["id"])
        conn.commit()
        for archive_path in archives:
            result = _import_one(conn, archive_path, dataset_id)
            results.append(result)
            if progress is not None:
                progress(result)
    finally:
        conn.close()
    return results
