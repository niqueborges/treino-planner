from __future__ import annotations

import sqlite3
import tempfile
import unittest
import zipfile
import warnings
from pathlib import Path

from app.db import connect
from app.importer import import_dataset

GIF_A = b"GIF89a\x01\x00\x01\x00test-media-a"
GIF_B = b"GIF89a\x02\x00\x01\x00test-media-b"


def write_zip(path: Path, entries: dict[str, bytes | None]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, value in entries.items():
            if value is None:
                archive.writestr(name.rstrip("/") + "/", b"")
            else:
                archive.writestr(name, value)


class ImportDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "library.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def counts(self) -> tuple[int, ...]:
        conn = connect(self.db_path)
        try:
            return tuple(conn.execute(
                "SELECT (SELECT COUNT(*) FROM dataset), "
                "(SELECT COUNT(*) FROM source_archive), "
                "(SELECT COUNT(*) FROM original_path), "
                "(SELECT COUNT(*) FROM exercise), "
                "(SELECT COUNT(*) FROM media_asset), "
                "(SELECT COUNT(*) FROM exercise_media)"
            ).fetchone())
        finally:
            conn.close()

    def test_import_is_idempotent_and_keeps_duplicate_occurrences(self) -> None:
        first = self.root / "set-001.zip"
        second = self.root / "set-002.zip"
        write_zip(first, {
            "Dataset/FEMININO/ACADEMIA/HALTERES/PERNA/leg.gif": GIF_A,
            "Dataset/FEMININO/ACADEMIA/HALTERES/PERNA/leg-copy.gif": GIF_A,
            "Dataset/FEMININO/ACADEMIA/HALTERES/desktop.ini": b"folder settings",
            "Dataset/FEMININO/ACADEMIA/EMPTY/": None,
        })

        initial = import_dataset([first], self.db_path)
        self.assertEqual(initial[0]["gif_occurrences"], 2)
        self.assertEqual(initial[0]["new_media"], 1)
        self.assertEqual(self.counts(), (1, 1, 4, 2, 1, 2))

        repeated = import_dataset([first], self.db_path)
        self.assertTrue(repeated[0]["skipped"])
        self.assertEqual(self.counts(), (1, 1, 4, 2, 1, 2))

        write_zip(second, {"Dataset/MASCULINO/FUNCIONAL/PESO/leg.gif": GIF_A})
        added = import_dataset([second], self.db_path)
        self.assertEqual(added[0]["gif_occurrences"], 1)
        self.assertEqual(added[0]["new_media"], 0)
        self.assertEqual(self.counts(), (1, 2, 5, 3, 1, 3))

        conn = connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM exercise WHERE identification_status='pending'").fetchone()[0], 3)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM category").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM muscle_group").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM original_path WHERE entry_type='directory'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM source_metadata WHERE value_raw='HALTERES'").fetchone()[0], 3)
        finally:
            conn.close()
        self.assertEqual(sorted(p.name for p in self.root.glob("*.zip")), ["set-001.zip", "set-002.zip"])

    def test_changed_archive_is_a_new_snapshot_and_preserves_old_occurrence(self) -> None:
        source = self.root / "dataset.zip"
        member = "Dataset/FEMININO/FUNCIONAL/step.gif"
        write_zip(source, {member: GIF_A})
        import_dataset([source], self.db_path)
        write_zip(source, {member: GIF_B})
        result = import_dataset([source], self.db_path)
        self.assertFalse(result[0]["skipped"])
        self.assertEqual(self.counts(), (1, 2, 2, 2, 2, 2))
        conn = connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(DISTINCT path_raw) FROM original_path").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM media_asset").fetchone()[0], 2)
        finally:
            conn.close()

    def test_directory_input_finds_zips_recursively(self) -> None:
        folder = self.root / "incoming" / "nested"
        folder.mkdir(parents=True)
        zip_path = folder / "part.zip"
        write_zip(zip_path, {"Dataset/MASCULINO/ACADEMIA/CARDIO/run.gif": GIF_A})
        result = import_dataset([self.root / "incoming"], self.db_path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["gif_occurrences"], 1)

    def test_same_internal_path_repeated_in_one_zip_is_kept_as_two_occurrences(self) -> None:
        source = self.root / "repeated-path.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("Dataset/FEMININO/FUNCIONAL/repeated.gif", GIF_A)
                archive.writestr("Dataset/FEMININO/FUNCIONAL/repeated.gif", GIF_B)
        result = import_dataset([source], self.db_path)
        self.assertEqual(result[0]["gif_occurrences"], 2)
        self.assertEqual(self.counts(), (1, 1, 2, 2, 2, 2))


if __name__ == "__main__":
    unittest.main()
