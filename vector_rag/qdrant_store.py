import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from .config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL_NAME,
    QDRANT_COLLECTION,
    QDRANT_URL,
    TOP_K,
)


class QdrantVectorStore:
    def __init__(
        self,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION,
        embedding_model_name=EMBEDDING_MODEL_NAME,
    ):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)
        self.embedding_model = SentenceTransformer(embedding_model_name)

    def init_collection(self):
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIM,
                distance=models.Distance.COSINE,
            ),
        )

    def embed(self, texts):
        return self.embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    def upsert_chunks(self, chunks, source):
        self.init_collection()
        vectors = self.embed(chunks)
        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "text": chunk,
                        "source": source,
                        "chunk_index": idx,
                    },
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(self, query, top_k=TOP_K):
        self.init_collection()
        query_vector = self.embed([query])[0]
        try:
            hits = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )
        except AttributeError:
            result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )
            hits = result.points

        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "text": payload.get("text", ""),
                    "source": payload.get("source", ""),
                    "chunk_index": payload.get("chunk_index"),
                    "score": float(hit.score),
                }
            )
        return results


def format_vector_context(results):
    if not results:
        return ""
    lines = []
    for idx, item in enumerate(results, start=1):
        source = item.get("source") or "unknown"
        score = item.get("score", 0)
        text = item.get("text", "")
        lines.append(f"[Vector {idx}] source={source}, score={score:.4f}\n{text}")
    return "\n\n".join(lines)
