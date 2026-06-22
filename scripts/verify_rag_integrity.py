"""
QA integrity checks for the CivicEase AI RAG ingestion pipeline.

This script is intentionally non-destructive:
- It reads the real Chroma ingestion manifest.
- It validates deterministic chunk IDs against the real knowledge base.
- It simulates a file update using a temporary copy, not the production data file.

Run from the project root:
    python scripts/verify_rag_integrity.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.rag_engine import (  # noqa: E402
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_PATH,
    MANIFEST_PATH,
    _fingerprint_file,
    _iter_source_files,
    _prepare_chunks,
)


class CheckFailure(RuntimeError):
    """Raised when a QA check fails."""


def _pass(message: str) -> None:
    print(f"[PASS] {message}")


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise CheckFailure(
            f"Manifest not found at {MANIFEST_PATH}. Run `python core/rag_engine.py` first."
        )

    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"Manifest exists but is not valid JSON: {exc}") from exc

    if not isinstance(manifest, dict):
        raise CheckFailure("Manifest root must be a JSON object keyed by source filename.")

    _pass(f"Manifest exists and is valid JSON: {MANIFEST_PATH}")
    return manifest


def check_manifest_schema(manifest: dict) -> None:
    required_fields = {
        "source",
        "md5",
        "last_modified_ns",
        "size_bytes",
        "chunk_count",
        "chunk_size",
        "chunk_overlap",
    }

    if not manifest:
        raise CheckFailure("Manifest is empty; no ingested source files are tracked.")

    for source, record in manifest.items():
        if not isinstance(record, dict):
            raise CheckFailure(f"Manifest record for {source!r} is not an object.")
        missing = required_fields - set(record)
        if missing:
            raise CheckFailure(f"Manifest record for {source!r} is missing fields: {sorted(missing)}")
        if record["chunk_size"] != CHUNK_SIZE or record["chunk_overlap"] != CHUNK_OVERLAP:
            raise CheckFailure(
                f"Manifest chunk config mismatch for {source!r}: "
                f"{record['chunk_size']}/{record['chunk_overlap']} != {CHUNK_SIZE}/{CHUNK_OVERLAP}"
            )

    _pass(f"Manifest schema is valid for {len(manifest)} tracked source file(s).")


def check_manifest_matches_files(manifest: dict) -> None:
    source_files = {path.name: path for path in _iter_source_files(DATA_PATH)}
    if not source_files:
        raise CheckFailure(f"No supported .md or .txt files found in {DATA_PATH}.")

    missing_on_disk = sorted(set(manifest) - set(source_files))
    not_manifested = sorted(set(source_files) - set(manifest))

    if missing_on_disk:
        print(f"[WARN] Manifest tracks deleted or moved file(s): {missing_on_disk}")
    if not_manifested:
        print(f"[WARN] Source file(s) not yet in manifest: {not_manifested}")

    for source, file_path in source_files.items():
        if source not in manifest:
            continue
        current = _fingerprint_file(file_path)
        recorded = manifest[source]
        if current.md5 != recorded["md5"]:
            print(f"[WARN] Source changed since last ingestion: {source}")
            continue
        if current.size_bytes != recorded["size_bytes"]:
            print(f"[WARN] Size changed without MD5 match for {source}; inspect filesystem state.")

    _pass("Manifest-to-filesystem comparison completed.")


def check_deterministic_chunk_ids(source_file: Path) -> None:
    ids_a, texts_a, metadata_a = _prepare_chunks(source_file)
    ids_b, texts_b, metadata_b = _prepare_chunks(source_file)

    if not ids_a:
        raise CheckFailure(f"No chunks generated for {source_file.name}.")
    if ids_a != ids_b:
        raise CheckFailure("Chunk IDs are not deterministic across repeated runs.")
    if texts_a != texts_b:
        raise CheckFailure("Chunk text output is not deterministic across repeated runs.")
    if len(ids_a) != len(set(ids_a)):
        raise CheckFailure("Duplicate chunk IDs were generated within one source file.")
    if any(meta.get("chunk_size") != CHUNK_SIZE for meta in metadata_a):
        raise CheckFailure("At least one chunk metadata record has an unexpected chunk_size.")
    if any(meta.get("chunk_overlap") != CHUNK_OVERLAP for meta in metadata_a):
        raise CheckFailure("At least one chunk metadata record has an unexpected chunk_overlap.")

    _pass(
        f"Deterministic chunk ID check passed for {source_file.name}: "
        f"{len(ids_a)} unique chunk(s)."
    )


def check_mock_update_detection(source_file: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="civicease_rag_qa_") as temp_dir:
        temp_path = Path(temp_dir) / source_file.name
        shutil.copy2(source_file, temp_path)

        before = _fingerprint_file(temp_path)
        with temp_path.open("a", encoding="utf-8") as handle:
            handle.write("\n\n<!-- QA mock update: verifies fingerprint change detection. -->\n")
        after = _fingerprint_file(temp_path)

    if before.md5 == after.md5:
        raise CheckFailure("Mock update did not change the MD5 fingerprint.")
    if before.last_modified_ns == after.last_modified_ns and before.size_bytes == after.size_bytes:
        raise CheckFailure("Mock update did not change timestamp or size metadata.")

    _pass(
        "Mock update detection passed: MD5 changed "
        f"{before.md5[:8]} -> {after.md5[:8]}."
    )


def choose_source_file(manifest: dict, requested: str | None) -> Path:
    source_files = {path.name: path for path in _iter_source_files(DATA_PATH)}
    if requested:
        requested_path = Path(requested)
        if requested_path.exists():
            return requested_path
        if requested in source_files:
            return source_files[requested]
        raise CheckFailure(f"Requested source file was not found: {requested}")

    manifested_sources = [source for source in manifest if source in source_files]
    if manifested_sources:
        return source_files[manifested_sources[0]]

    if source_files:
        return next(iter(source_files.values()))

    raise CheckFailure(f"No supported source files found in {DATA_PATH}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify CivicEase AI RAG ingestion integrity.")
    parser.add_argument(
        "--source",
        help="Optional source filename or path to use for chunk-ID and mock-update checks.",
    )
    args = parser.parse_args()

    print("CivicEase AI RAG Integrity Verification")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Chunk config: size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")

    try:
        manifest = load_manifest()
        check_manifest_schema(manifest)
        check_manifest_matches_files(manifest)
        source_file = choose_source_file(manifest, args.source)
        check_deterministic_chunk_ids(source_file)
        check_mock_update_detection(source_file)
    except CheckFailure as exc:
        _fail(str(exc))
        return 1

    print("[PASS] RAG pipeline integrity checks completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
