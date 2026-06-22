import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Optional

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = PROJECT_ROOT / "chroma_db"
DATA_PATH = PROJECT_ROOT / "data"
MANIFEST_PATH = CHROMA_PATH / "ingestion_manifest.json"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "langchain")
SUPPORTED_EXTENSIONS = {".txt", ".md"}

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

_INGESTION_LOCK = Lock()

US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new_hampshire", "new_jersey", "new_mexico", "new_york",
    "north_carolina", "north_dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode_island", "south_carolina", "south_dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west_virginia", "wisconsin", "wyoming",
}

KNOWN_PROGRAMS = {
    "snap", "wic", "tanf", "medicaid", "chip", "ccdf", "eitc",
    "ssi", "nslp", "sbp", "liheap", "housing", "childcare",
}


@dataclass(frozen=True)
class FileFingerprint:
    """Stable change-detection metadata for incremental ingestion."""

    source: str
    md5: str
    last_modified_ns: int
    size_bytes: int


@dataclass(frozen=True)
class MCPRoadmapConfig:
    """
    Architectural placeholder for the CivicEase AI Model Context Protocol path.

    Today, the three-agent pipeline calls Python functions directly:
    Agent 1 structures intake, Agent 2 queries ChromaDB, and Agent 3 builds an
    action plan. MCP can standardize those boundaries as explicit tools such as
    `policy_vector_search`, `policy_document_upsert`, and `external_policy_api`.
    When CivicEase moves to MCP, these tool contracts should expose typed inputs,
    scoped credentials, auditable outputs, and least-privilege access to ChromaDB
    and trusted government policy APIs.
    """

    enabled: bool = False
    vector_search_tool: str = "civicease.policy_vector_search"
    vector_upsert_tool: str = "civicease.policy_document_upsert"
    policy_api_tool: str = "civicease.external_policy_api"
    agent_namespace: str = "civicease.three_agent_pipeline"


def _extract_metadata_from_filename(filename: str) -> dict:
    stem = Path(filename).stem.lower()
    meta = {}

    state_tag = next(
        (state for state in sorted(US_STATES, key=len, reverse=True) if stem == state or stem.startswith(f"{state}_")),
        None,
    )
    program_tag = next(
        (program for program in KNOWN_PROGRAMS if stem == program or f"_{program}" in f"_{stem}"),
        None,
    )

    if state_tag:
        meta["state"] = state_tag
    if program_tag:
        meta["program"] = program_tag
    return meta


@lru_cache(maxsize=1)
def _embedding_function() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def _vector_store() -> Chroma:
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        persist_directory=str(CHROMA_PATH),
        embedding_function=_embedding_function(),
    )


def _text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True,
    )


def _iter_source_files(data_path: Path = DATA_PATH) -> list[Path]:
    if not data_path.exists():
        return []
    return [
        path
        for path in sorted(data_path.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def _fingerprint_file(file_path: Path) -> FileFingerprint:
    digest = hashlib.md5()
    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    stat = file_path.stat()
    return FileFingerprint(
        source=file_path.name,
        md5=digest.hexdigest(),
        last_modified_ns=stat.st_mtime_ns,
        size_bytes=stat.st_size,
    )


def _load_manifest() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read ingestion manifest; rebuilding it: %s", exc)
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_manifest(manifest: dict[str, dict]) -> None:
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(CHROMA_PATH),
        delete=False,
    ) as tmp:
        json.dump(manifest, tmp, indent=2, sort_keys=True)
        tmp_path = Path(tmp.name)
    tmp_path.replace(MANIFEST_PATH)


def _load_documents(file_path: Path) -> list[Document]:
    header_regex = re.compile(
        r"^##\s+State Deep Dive\s+[-\u2013\u2014]\s+(.+?)\s+\(([A-Z]{2})\)\s*$",
        re.MULTILINE,
    )

    if file_path.name != "civicease_knowledge_base.md":
        loader = TextLoader(str(file_path), encoding="utf-8")
        docs = loader.load()
        file_meta = _extract_metadata_from_filename(file_path.name)
        for doc in docs:
            doc.metadata.update(file_meta)
            doc.metadata.setdefault("source", file_path.name)
        return docs

    content = file_path.read_text(encoding="utf-8")
    matches = list(header_regex.finditer(content))
    if not matches:
        loader = TextLoader(str(file_path), encoding="utf-8")
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = file_path.name
        return docs

    documents: list[Document] = []
    intro_text = content[:matches[0].start()].strip()
    if intro_text:
        documents.append(Document(page_content=intro_text, metadata={"source": file_path.name}))

    for index, match in enumerate(matches):
        state_name = match.group(1).strip().lower().replace(" ", "_")
        start_pos = match.start()
        end_pos = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section_text = content[start_pos:end_pos].strip()
        documents.append(
            Document(
                page_content=section_text,
                metadata={"source": file_path.name, "state": state_name},
            )
        )

    return documents


def _chunk_id(source: str, chunk: Document, ordinal: int) -> str:
    start_index = chunk.metadata.get("start_index", ordinal)
    state = chunk.metadata.get("state", "global")
    content_hash = hashlib.sha256(chunk.page_content.encode("utf-8")).hexdigest()[:16]
    raw_id = f"{source}:{state}:{start_index}:{content_hash}"
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()


def _prepare_chunks(file_path: Path) -> tuple[list[str], list[str], list[dict]]:
    documents = _load_documents(file_path)
    chunks = _text_splitter().split_documents(documents)

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []
    for ordinal, chunk in enumerate(chunks):
        metadata = {
            key: value
            for key, value in chunk.metadata.items()
            if value is not None and isinstance(value, (str, int, float, bool))
        }
        metadata["source"] = file_path.name
        metadata["chunk_ordinal"] = ordinal
        metadata["chunk_size"] = CHUNK_SIZE
        metadata["chunk_overlap"] = CHUNK_OVERLAP

        ids.append(_chunk_id(file_path.name, chunk, ordinal))
        texts.append(chunk.page_content)
        metadatas.append(metadata)
    return ids, texts, metadatas


def _remove_stale_chunks(collection, source: str, active_ids: set[str]) -> int:
    existing = collection.get(where={"source": source}, include=[])
    existing_ids = set(existing.get("ids", []))
    stale_ids = sorted(existing_ids - active_ids)
    if stale_ids:
        collection.delete(ids=stale_ids)
    return len(stale_ids)


def upsert_document(file_path: Path, db: Optional[Chroma] = None) -> dict:
    """
    Split one source file into 800-character chunks with 150-character overlap
    and upsert them into ChromaDB with predictable document IDs.

    Existing chunks with matching IDs are overwritten in place. Chunks that were
    produced by an older version of the same source file but no longer exist are
    deleted by ID only; the vector database is never wiped wholesale.
    """

    vector_db = db or _vector_store()
    collection = vector_db._collection
    ids, texts, metadatas = _prepare_chunks(file_path)
    if not ids:
        return {"source": file_path.name, "upserted": 0, "deleted_stale": 0}

    embeddings = _embedding_function().embed_documents(texts)
    collection.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    deleted_stale = _remove_stale_chunks(collection, file_path.name, set(ids))
    if hasattr(vector_db, "persist"):
        vector_db.persist()
    return {"source": file_path.name, "upserted": len(ids), "deleted_stale": deleted_stale}


def sync_vector_db(data_path: Path = DATA_PATH) -> dict:
    """
    Incrementally synchronize local policy files into ChromaDB.

    Change detection uses both file metadata and an MD5 content hash. Unchanged
    files are skipped, changed files are re-chunked and upserted, and missing
    source files have only their own chunks removed. This design supports
    background execution while the Flask API continues serving reads.
    """

    with _INGESTION_LOCK:
        source_files = _iter_source_files(data_path)
        if not source_files:
            logger.warning("No .txt or .md knowledge-base files found in %s", data_path)
            return {"processed": [], "skipped": [], "removed": [], "total_sources": 0}

        manifest = _load_manifest()
        changed_files: list[tuple[Path, FileFingerprint]] = []
        skipped: list[str] = []
        current_sources: set[str] = set()

        for file_path in source_files:
            fingerprint = _fingerprint_file(file_path)
            current_sources.add(fingerprint.source)
            previous = manifest.get(fingerprint.source)

            if previous and previous.get("md5") == fingerprint.md5:
                skipped.append(fingerprint.source)
                continue

            changed_files.append((file_path, fingerprint))

        removed_sources = sorted(set(manifest) - current_sources)
        if not changed_files and not removed_sources:
            return {
                "processed": [],
                "skipped": skipped,
                "removed": [],
                "total_sources": len(source_files),
            }

        db = _vector_store()
        collection = db._collection

        processed: list[dict] = []
        for file_path, fingerprint in changed_files:
            result = upsert_document(file_path, db=db)
            processed.append(result)
            manifest[fingerprint.source] = {
                **asdict(fingerprint),
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
                "chunk_count": result["upserted"],
            }
            logger.info("Upserted %s chunks for %s", result["upserted"], fingerprint.source)

        removed: list[str] = []
        for source in removed_sources:
            existing = collection.get(where={"source": source}, include=[])
            ids = existing.get("ids", [])
            if ids:
                collection.delete(ids=ids)
            manifest.pop(source, None)
            removed.append(source)
            logger.info("Removed %s stale chunks for deleted source %s", len(ids), source)

        if processed or removed:
            if hasattr(db, "persist"):
                db.persist()
            _save_manifest(manifest)

        return {
            "processed": processed,
            "skipped": skipped,
            "removed": removed,
            "total_sources": len(source_files),
        }


def build_vector_db():
    """Backward-compatible entry point used by setup scripts and local rebuilds."""

    result = sync_vector_db(DATA_PATH)
    print(
        "Vector DB sync complete: "
        f"{len(result['processed'])} processed, "
        f"{len(result['skipped'])} skipped, "
        f"{len(result['removed'])} removed."
    )
    if result["processed"] or result["removed"]:
        return _vector_store()
    return None


def get_retriever(metadata_filter: Optional[dict] = None):
    if not CHROMA_PATH.exists():
        raise FileNotFoundError(f"Chroma database not found at '{CHROMA_PATH}'. Run build_vector_db first.")

    db = _vector_store()
    search_kwargs: dict = {"k": 5}

    clean_filter = {key: value for key, value in (metadata_filter or {}).items() if value}
    if clean_filter:
        search_kwargs["filter"] = clean_filter

    return db.as_retriever(search_kwargs=search_kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    build_vector_db()
