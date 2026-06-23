from pathlib import Path

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .loaders import load_document
from .qdrant_store import QdrantVectorStore
from .text_splitter import split_text


def ingest_file(path, store=None, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    path = Path(path)
    store = store or QdrantVectorStore()
    text = load_document(path)
    chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    inserted = store.upsert_chunks(chunks, source=path.name)
    return {
        "source": path.name,
        "chunks": len(chunks),
        "inserted": inserted,
    }
