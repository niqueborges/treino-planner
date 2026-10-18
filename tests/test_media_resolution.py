from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.db import connect
from app.importer import import_dataset
from app.web import LibraryHandler

ROOT_PREFIX = "GIFS PLANEJADOR - ORGANIZADOS/"
DIRECT_PATH = ROOT_PREFIX + "MASCULINO/ACADEMIA/HALTERES/direct.gif"
AZ_PATH = ROOT_PREFIX + "FEMININO/FUNCIONAL/az-example.gif"
REMOVED_PATH = ROOT_PREFIX + "MASCULINO/ACADEMIA/HALTERES/removed.gif"
RETAINED_PATH = ROOT_PREFIX + "MASCULINO/ACADEMIA/HALTERES/retained.gif"
MISMATCH_PATH = ROOT_PREFIX + "MASCULINO/ACADEMIA/HALTERES/mismatch.gif"
TRAVERSAL_PATH = "../outside.gif"
ZIP_ONLY_PATH = ROOT_PREFIX + "MASCULINO/ACADEMIA/HALTERES/zip-only.gif"

DIRECT_DATA = b"GIF89a direct tree media"
AZ_DATA = b"GIF89a A-Z reorganized media"
DUPLICATE_DATA = b"GIF89a duplicate exact content"
ZIP_DATA = b"GIF89a expected ZIP fallback"
OUTSIDE_DATA = b"GIF89a MUST NOT BE SERVED"


class MediaResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp.name)
        self.dataset_root = self.temp_root / "dataset-original"
        self.dataset_root.mkdir()
        self.db_path = self.temp_root / "library.sqlite3"
        self.zip_path = self.temp_root / "source.zip"
        entries = {
            DIRECT_PATH: DIRECT_DATA,
            AZ_PATH: AZ_DATA,
            REMOVED_PATH: DUPLICATE_DATA,
            RETAINED_PATH: DUPLICATE_DATA,
            MISMATCH_PATH: ZIP_DATA,
            TRAVERSAL_PATH: ZIP_DATA,
            ZIP_ONLY_PATH: ZIP_DATA,
        }
        with zipfile.ZipFile(self.zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        import_dataset([self.zip_path], self.db_path)

        self._write_tree(DIRECT_PATH, DIRECT_DATA)
        az_target = self.dataset_root / ROOT_PREFIX / "FEMININO/FUNCIONAL/SEM CATEGORIA ORIGINAL/A/az-example.gif"
        az_target.parent.mkdir(parents=True, exist_ok=True)
        az_target.write_bytes(AZ_DATA)
        self._write_tree(RETAINED_PATH, DUPLICATE_DATA)
        self._write_tree(MISMATCH_PATH, b"GIF89a corrupt tree copy")
        (self.temp_root / "outside.gif").write_bytes(OUTSIDE_DATA)

        self._previous_dataset_root = os.environ.get("TREINO_PLANNER_DATASET_ROOT")
        os.environ["TREINO_PLANNER_DATASET_ROOT"] = str(self.dataset_root)
        handler = partial(LibraryHandler, db_path=self.db_path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self._previous_dataset_root is None:
            os.environ.pop("TREINO_PLANNER_DATASET_ROOT", None)
        else:
            os.environ["TREINO_PLANNER_DATASET_ROOT"] = self._previous_dataset_root
        self.temp.cleanup()

    def _write_tree(self, relative_path: str, content: bytes) -> None:
        target = self.dataset_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def media_id(self, path_raw: str) -> int:
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT ma.id FROM media_asset ma JOIN exercise_media em ON em.media_asset_id=ma.id "
                "JOIN original_path op ON op.id=em.original_path_id WHERE op.path_raw=?",
                (path_raw,),
            ).fetchone()
            self.assertIsNotNone(row)
            return int(row["id"])
        finally:
            conn.close()

    def get_media(self, path_raw: str) -> tuple[int, str, bytes]:
        request = urllib.request.Request(f"{self.base_url}/api/media/{self.media_id(path_raw)}")
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()

    def assert_media(self, path_raw: str, expected: bytes) -> None:
        status, content_type, body = self.get_media(path_raw)
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/gif")
        self.assertEqual(len(body), len(expected))
        self.assertEqual(hashlib.sha256(body).digest(), hashlib.sha256(expected).digest())

    def test_serves_verified_media_directly_from_original_relative_path(self) -> None:
        self.zip_path.rename(self.zip_path.with_suffix(".offline"))
        self.assert_media(DIRECT_PATH, DIRECT_DATA)

    def test_resolves_reorganized_feminine_functional_a_to_z_path(self) -> None:
        self.zip_path.rename(self.zip_path.with_suffix(".offline"))
        self.assert_media(AZ_PATH, AZ_DATA)

    def test_removed_duplicate_resolves_another_occurrence_with_same_sha256(self) -> None:
        self.zip_path.rename(self.zip_path.with_suffix(".offline"))
        self.assert_media(REMOVED_PATH, DUPLICATE_DATA)

    def test_hash_mismatch_in_tree_is_rejected_and_zip_fallback_is_used(self) -> None:
        self.assert_media(MISMATCH_PATH, ZIP_DATA)

    def test_path_traversal_outside_root_is_rejected_and_zip_fallback_is_used(self) -> None:
        self.assert_media(TRAVERSAL_PATH, ZIP_DATA)

    def test_zip_behavior_is_preserved_when_dataset_root_is_unset(self) -> None:
        os.environ.pop("TREINO_PLANNER_DATASET_ROOT", None)
        self.assert_media(ZIP_ONLY_PATH, ZIP_DATA)


if __name__ == "__main__":
    unittest.main()
