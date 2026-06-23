import argparse
from pathlib import Path

from vector_rag import QdrantVectorStore, ingest_file


def main():
    parser = argparse.ArgumentParser(description="Import medical pdf/txt files to Qdrant.")
    parser.add_argument("paths", nargs="+", help="PDF/TXT files or directories.")
    args = parser.parse_args()

    store = QdrantVectorStore()
    files = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if path.is_dir():
            files.extend(path.rglob("*.pdf"))
            files.extend(path.rglob("*.txt"))
        else:
            files.append(path)

    for path in files:
        result = ingest_file(path, store=store)
        print(
            f"Imported {result['source']}: "
            f"{result['inserted']}/{result['chunks']} chunks"
        )


if __name__ == "__main__":
    main()
