import datetime
import uuid
from backend.core.logger import logger

class MemoryManager:
    def __init__(self):
        logger.info("  [Module] MemoryManager initialized.")
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            # For demonstration and standalone testing, we use memory storage.
            # In production, this would point to a local Qdrant server instance.
            self.client = QdrantClient(":memory:")
            self.collection_name = "jarvis_memory"
            
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
                )
            self._use_mock = False
        except ImportError:
            logger.warning("[MemoryManager] qdrant-client not found. Falling back to native mock engine.")
            self._use_mock = True
            self._mock_db = []

    def _mock_embedding(self, text: str) -> list:
        # Generate a dummy 384-dimensional vector for exact Qdrant schema compliance without heavy ML models
        return [0.1] * 384

    def add_memory(self, memory_type: str, content: str, metadata: dict = None) -> bool:
        if memory_type not in ["short_term", "long_term", "profile"]:
            logger.error(f"[MemoryManager] Invalid memory type: {memory_type}")
            return False

        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        meta = metadata or {}
        meta.update({"type": memory_type, "timestamp": timestamp, "content": content})
        
        logger.info(f"[MemoryManager] Storing {memory_type} memory: '{content}'")

        if self._use_mock:
            self._mock_db.append({
                "id": str(uuid.uuid4()),
                "vector": self._mock_embedding(content),
                "payload": meta
            })
            return True

        from qdrant_client.http import models
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=self._mock_embedding(content),
                    payload=meta
                )
            ]
        )
        return True

    def retrieve_memory(self, query: str, memory_type: str = None) -> list:
        logger.info(f"[MemoryManager] Retrieving memory for query: '{query}' (type filter: {memory_type})")
        
        if self._use_mock:
            # Fallback exact string matching if Qdrant isn't installed
            results = []
            for item in self._mock_db:
                if memory_type and item["payload"]["type"] != memory_type:
                    continue
                if query.lower() in item["payload"]["content"].lower():
                    results.append({
                        "type": item["payload"]["type"],
                        "content": item["payload"]["content"],
                        "score": 1.0,
                        "timestamp": item["payload"]["timestamp"]
                    })
            return results

        from qdrant_client.http import models
        filter_cond = None
        if memory_type:
            filter_cond = models.Filter(
                must=[models.FieldCondition(key="type", match=models.MatchValue(value=memory_type))]
            )

        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=self._mock_embedding(query),
            query_filter=filter_cond,
            limit=5
        )

        formatted_results = []
        for hit in search_result:
            formatted_results.append({
                "type": hit.payload.get("type"),
                "content": hit.payload.get("content"),
                "score": round(hit.score, 4),
                "timestamp": hit.payload.get("timestamp")
            })
            
        return formatted_results

    def clear_session_memory(self):
        logger.info("[MemoryManager] Clearing short_term session memory...")
        if self._use_mock:
            self._mock_db = [item for item in self._mock_db if item["payload"]["type"] != "short_term"]
            logger.info("[MemoryManager] Session memory cleared (Mock Engine).")
            return

        from qdrant_client.http import models
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="type", match=models.MatchValue(value="short_term"))]
                )
            )
        )
        logger.info("[MemoryManager] Session memory cleared from Qdrant.")
