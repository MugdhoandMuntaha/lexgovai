"""ChromaDB-backed vector store for SOP chunks. Embeddings are computed by the LLM client, not Chroma."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from .documents import Chunk

COLLECTION = "sop_chunks"
COLLECTION_LAWS = "law_sections"


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    section: str
    text: str
    distance: float


@dataclass(frozen=True)
class RetrievedLawSection:
    section_id: str
    law_id: str
    version_id: str
    number_label: str
    heading: str
    text: str
    distance: float
    language: str = "en"
    status: str = "in_force"


class VectorStore:
    def __init__(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )
        self._law_collection = self._client.get_or_create_collection(
            name=COLLECTION_LAWS,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def count(self) -> int:
        """Returns total number of chunks stored in the SOP collection."""
        return self._collection.count()

    def add_document(self, document_id: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.add(
            ids=[f"{document_id}:{c.index}" for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[{"document_id": document_id, "section": c.section, "index": c.index} for c in chunks],
        )

    def query(self, document_id: str, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        available = len(self._collection.get(where={"document_id": document_id}, include=[])["ids"])
        if available == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, available),
            where={"document_id": document_id},
            include=["documents", "metadatas", "distances"],
        )
        return [
            RetrievedChunk(chunk_id=cid, section=str(meta["section"]), text=doc, distance=float(dist))
            for cid, doc, meta, dist in zip(
                result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
        ]

    def add_law_sections(
        self,
        law_id: str,
        version_id: str,
        sections: list[dict[str, Any]],
        embeddings: list[list[float]],
        language: str = "en",
        status: str = "in_force",
    ) -> None:
        """Indexes structured law sections into the law_sections ChromaDB collection."""
        if not sections or not embeddings:
            return
        ids = [f"{version_id}:{s['id']}" for s in sections]
        documents = [f"{s.get('number_label', '')} {s.get('heading', '')}\n{s.get('text', '')}".strip() for s in sections]
        metadatas = [
            {
                "law_id": law_id,
                "version_id": version_id,
                "section_id": s["id"],
                "number_label": s.get("number_label", ""),
                "heading": s.get("heading", "") or "",
                "language": language,
                "status": status,
            }
            for s in sections
        ]
        self._law_collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query_law_sections(
        self,
        embedding: list[float],
        top_k: int = 10,
        law_id: str | None = None,
        status: str | None = None,
    ) -> list[RetrievedLawSection]:
        """Performs cosine semantic search over law sections with optional law_id filter."""
        where_filter: dict[str, Any] | None = None
        if law_id and status:
            where_filter = {"$and": [{"law_id": law_id}, {"status": status}]}
        elif law_id:
            where_filter = {"law_id": law_id}
        elif status:
            where_filter = {"status": status}

        available = len(self._law_collection.get(where=where_filter, include=[])["ids"]) if where_filter else self._law_collection.count()
        if available == 0:
            return []

        kwargs: dict[str, Any] = {
            "query_embeddings": [embedding],
            "n_results": min(top_k, available),
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter

        result = self._law_collection.query(**kwargs)
        if not result["ids"] or not result["ids"][0]:
            return []

        hits: list[RetrievedLawSection] = []
        for cid, doc, meta, dist in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            hits.append(
                RetrievedLawSection(
                    section_id=str(meta.get("section_id", cid)),
                    law_id=str(meta.get("law_id", "")),
                    version_id=str(meta.get("version_id", "")),
                    number_label=str(meta.get("number_label", "")),
                    heading=str(meta.get("heading", "")),
                    text=doc,
                    distance=float(dist),
                    language=str(meta.get("language", "en")),
                    status=str(meta.get("status", "in_force")),
                )
            )
        return hits

    def delete_law_version_sections(self, version_id: str) -> None:
        """Removes all section embeddings for a given law version."""
        existing = self._law_collection.get(where={"version_id": version_id}, include=[])
        if existing["ids"]:
            self._law_collection.delete(ids=existing["ids"])


