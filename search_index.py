"""
Day 2 - Step 1: Embeddings + Vector Search
Turns code chunks into searchable "fingerprints" (embeddings) and stores
them in ChromaDB so we can later ask natural-language questions like
"where is the signing logic?" and get back the right function.
"""
import chromadb
from sentence_transformers import SentenceTransformer

from code_chunker import CodeChunk, chunk_repo
from repo_observer import clone_repo


class CodeSearchIndex:
    def __init__(self, persist_dir: str = "workspace/vector_store", collection_name: str = "repo_code"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(collection_name)
        # Small, fast, local embedding model - no API key needed
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def _chunk_id(self, chunk: CodeChunk, idx: int) -> str:
        # Unique, stable ID per chunk
        return f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}:{idx}"

    def index_chunks(self, chunks: list[CodeChunk], batch_size: int = 64):
        """Embed every chunk and store it in ChromaDB."""
        print(f"[search_index] Embedding {len(chunks)} chunks...")

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.code for c in batch]
            embeddings = self.model.encode(texts).tolist()

            ids = [self._chunk_id(c, i + j) for j, c in enumerate(batch)]
            metadatas = [{
                "file_path": c.file_path,
                "symbol_name": c.symbol_name,
                "symbol_type": c.symbol_type,
                "start_line": c.start_line,
                "end_line": c.end_line,
            } for c in batch]

            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
        print(f"[search_index] Done. Indexed {len(chunks)} chunks.")

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Search the index with a natural-language query, return top-k matches."""
        query_embedding = self.model.encode([query]).tolist()
        results = self.collection.query(query_embeddings=query_embedding, n_results=k)

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            hits.append({
                "code": doc,
                "file_path": meta["file_path"],
                "symbol_name": meta["symbol_name"],
                "symbol_type": meta["symbol_type"],
                "start_line": meta["start_line"],
                "end_line": meta["end_line"],
                "distance": dist,  # lower = more similar
            })
        return hits


def build_index_for_repo(repo_url: str, dest_dir: str) -> CodeSearchIndex:
    repo_path = clone_repo(repo_url, dest_dir)
    chunks = chunk_repo(repo_path)
    index = CodeSearchIndex()
    index.index_chunks(chunks)
    return index


if __name__ == "__main__":
    index = build_index_for_repo(
        repo_url="https://github.com/pallets/itsdangerous.git",
        dest_dir="workspace/repos/itsdangerous",
    )

    # Sanity test: ask a real question about this codebase
    test_queries = [
        "verify a signed value",
        "handle an expired timestamp",
        "encode bytes to base64",
    ]
    for q in test_queries:
        print(f"\n=== Query: '{q}' ===")
        results = index.search(q, k=2)
        for r in results:
            print(f"  [{r['distance']:.3f}] {r['symbol_type']} {r['symbol_name']} "
                  f"({r['file_path']}:{r['start_line']})")