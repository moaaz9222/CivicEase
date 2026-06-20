import os
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = PROJECT_ROOT / "chroma_db"
DATA_PATH = PROJECT_ROOT / "data"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

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


def _embedding_function() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def build_vector_db():
    if not DATA_PATH.exists() or not any(DATA_PATH.iterdir()):
        print(f"Please add knowledge-base .txt or .md files to '{DATA_PATH}'.")
        return None

    from langchain_core.documents import Document
    import re

    documents = []
    header_regex = re.compile(r"^##\s+State Deep Dive\s+[—-]\s+(.+?)\s+\(([A-Z]{2})\)\s*$", re.MULTILINE)

    for file_path in sorted(DATA_PATH.iterdir()):
        if file_path.suffix.lower() not in {".txt", ".md"}:
            continue
        
        if file_path.name == "civicease_knowledge_base.md":
            content = file_path.read_text(encoding="utf-8")
            matches = list(header_regex.finditer(content))
            
            if not matches:
                loader = TextLoader(str(file_path), encoding="utf-8")
                docs = loader.load()
                for doc in docs:
                    doc.metadata["source"] = file_path.name
                documents.extend(docs)
                continue

            intro_text = content[:matches[0].start()].strip()
            if intro_text:
                documents.append(Document(
                    page_content=intro_text,
                    metadata={"source": file_path.name}
                ))

            for i, match in enumerate(matches):
                state_name = match.group(1).strip().lower().replace(" ", "_")
                start_pos = match.start()
                end_pos = matches[i+1].start() if i + 1 < len(matches) else len(content)
                section_text = content[start_pos:end_pos].strip()
                
                documents.append(Document(
                    page_content=section_text,
                    metadata={
                        "source": file_path.name,
                        "state": state_name
                    }
                ))
            print(f"Parsed {file_path.name} into {len(matches)} state sections.")
        else:
            loader = TextLoader(str(file_path), encoding="utf-8")
            docs = loader.load()
            file_meta = _extract_metadata_from_filename(file_path.name)
            for doc in docs:
                doc.metadata.update(file_meta)
                doc.metadata.setdefault("source", file_path.name)
            documents.extend(docs)
            print(f"Loaded: {file_path.name} metadata={file_meta or 'generic'}")

    if not documents:
        print("No valid text files found.")
        return None

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    embeddings = _embedding_function()
    db = Chroma.from_documents(chunks, embeddings, persist_directory=str(CHROMA_PATH))
    print(f"Vector DB built at '{CHROMA_PATH}'.")
    return db


def get_retriever(metadata_filter: Optional[dict] = None):
    if not CHROMA_PATH.exists():
        raise FileNotFoundError(f"Chroma database not found at '{CHROMA_PATH}'. Run build_vector_db first.")

    db = Chroma(persist_directory=str(CHROMA_PATH), embedding_function=_embedding_function())
    search_kwargs: dict = {"k": 4}

    clean_filter = {k: v for k, v in (metadata_filter or {}).items() if v}
    if clean_filter:
        search_kwargs["filter"] = clean_filter

    return db.as_retriever(search_kwargs=search_kwargs)


if __name__ == "__main__":
    build_vector_db()
