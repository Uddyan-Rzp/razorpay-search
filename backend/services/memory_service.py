"""
Memory Service for storing and retrieving query memories
Integrates with the existing backend configuration
"""
import os
import time
from typing import List, Dict, Optional
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, NearestQuery
from openai import AzureOpenAI
from config import Config


class MemoryService:
    """Service for managing query memories"""
    
    MEMORY_COLLECTION_NAME = "query_memory"
    
    def __init__(self):
        self.tenant_id = os.getenv("ORG_NAME", "default")
        self._initialize_client()
        self._initialize_embedding_client()
        self._ensure_collection()
    
    def _initialize_client(self):
        """Initialize Qdrant client using backend config"""
        from qdrant_client import QdrantClient
        
        if Config.QDRANT_API_KEY:
            self.qdrant = QdrantClient(
                url=Config.QDRANT_URL,
                api_key=Config.QDRANT_API_KEY
            )
        else:
            self.qdrant = QdrantClient(url=Config.QDRANT_URL)
        print(f"✓ Memory Service: Connected to Qdrant at {Config.QDRANT_URL}")
    
    def _initialize_embedding_client(self):
        """Initialize Azure OpenAI client for embeddings"""
        self.embedding_client = AzureOpenAI(
            api_key=Config.EMBEDDING_AZURE_API_KEY,
            azure_endpoint=Config.EMBEDDING_AZURE_ENDPOINT,
            api_version=Config.EMBEDDING_AZURE_API_VERSION
        )
        print("✓ Memory Service: Embedding client initialized")
    
    def _ensure_collection(self):
        """Ensure the memory collection exists"""
        try:
            collections = self.qdrant.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.MEMORY_COLLECTION_NAME not in collection_names:
                # Get vector size from embedding
                sample_embedding = self._embed("sample")
                vector_size = len(sample_embedding)
                
                from qdrant_client.models import VectorParams, Distance
                self.qdrant.create_collection(
                    collection_name=self.MEMORY_COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"✓ Memory Service: Created collection '{self.MEMORY_COLLECTION_NAME}'")
        except Exception as e:
            print(f"⚠ Memory Service: Error ensuring collection: {e}")
    
    def _embed(self, text: str) -> List[float]:
        """Generate embedding for text"""
        try:
            res = self.embedding_client.embeddings.create(
                model=Config.EMBEDDING_MODEL,
                input=text
            )
            return res.data[0].embedding
        except Exception as e:
            print(f"⚠ Memory Service: Embedding failed: {e}")
            raise
    
    def save_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        results_clicked: Optional[List[str]] = None,
        sources_searched: Optional[List[str]] = None,
        result_count: int = 0,
        metadata: Optional[Dict] = None
    ) -> int:
        """Save a query to memory"""
        timestamp = datetime.now().isoformat()
        query_id = int(time.time() * 1000000)  # microseconds for uniqueness
        
        # Create embedding
        vector = self._embed(query)
        
        # Build payload
        payload = {
            "query": query,
            "tenant_id": self.tenant_id,
            "timestamp": timestamp,
            "result_count": result_count,
            "type": "query_memory"
        }
        
        if user_id:
            payload["user_id"] = user_id
        if results_clicked:
            payload["results_clicked"] = results_clicked
            payload["click_count"] = len(results_clicked)
        if sources_searched:
            payload["sources_searched"] = sources_searched
        if metadata:
            payload.update(metadata)
        
        # Store in Qdrant
        self.qdrant.upsert(
            collection_name=self.MEMORY_COLLECTION_NAME,
            points=[
                PointStruct(
                    id=query_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
        
        return query_id
    
    def get_similar_queries(
        self,
        query: str,
        limit: int = 5,
        user_id: Optional[str] = None,
        min_score: float = 0.7
    ) -> List[Dict]:
        """Retrieve similar past queries"""
        query_vector = self._embed(query)
        
        # Build filter
        filter_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=self.tenant_id)
            )
        ]
        
        if user_id:
            filter_conditions.append(
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            )
        
        filter_condition = Filter(must=filter_conditions) if filter_conditions else None
        
        # Search for similar queries
        nearest_query = NearestQuery(nearest=query_vector)
        results = self.qdrant.query_points(
            collection_name=self.MEMORY_COLLECTION_NAME,
            query=nearest_query,
            query_filter=filter_condition,
            limit=limit,
            score_threshold=min_score
        )
        
        similar_queries = []
        for point in results.points:
            payload = point.payload or {}
            similar_queries.append({
                "query": payload.get("query", ""),
                "score": point.score,
                "timestamp": payload.get("timestamp"),
                "user_id": payload.get("user_id"),
                "click_count": payload.get("click_count", 0),
                "sources_searched": payload.get("sources_searched", []),
                "result_count": payload.get("result_count", 0)
            })
        
        return similar_queries
    
    def get_query_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        days_back: Optional[int] = None
    ) -> List[Dict]:
        """Get recent query history"""
        filter_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=self.tenant_id)
            )
        ]
        
        if user_id:
            filter_conditions.append(
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            )
        
        filter_condition = Filter(must=filter_conditions)
        
        # Scroll through queries
        results = self.qdrant.scroll(
            collection_name=self.MEMORY_COLLECTION_NAME,
            scroll_filter=filter_condition,
            limit=limit * 2,
            with_payload=True,
            with_vectors=False
        )
        
        queries = []
        for point in results[0]:
            payload = point.payload or {}
            queries.append({
                "query": payload.get("query", ""),
                "timestamp": payload.get("timestamp"),
                "user_id": payload.get("user_id"),
                "click_count": payload.get("click_count", 0),
                "sources_searched": payload.get("sources_searched", []),
                "result_count": payload.get("result_count", 0)
            })
        
        # Sort by timestamp (newest first)
        queries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Filter by days_back if specified
        if days_back:
            cutoff_time = time.time() - (days_back * 24 * 60 * 60)
            queries = [q for q in queries if q.get("timestamp") and 
                      datetime.fromisoformat(q["timestamp"]).timestamp() > cutoff_time]
        
        return queries[:limit]
    
    def get_popular_queries(
        self,
        limit: int = 10,
        days_back: int = 7
    ) -> List[Dict]:
        """Get most popular queries"""
        recent_queries = self.get_query_history(limit=1000, days_back=days_back)
        
        # Aggregate by query text
        query_stats = {}
        for q in recent_queries:
            query_text = q["query"]
            if query_text not in query_stats:
                query_stats[query_text] = {
                    "query": query_text,
                    "count": 0,
                    "total_clicks": 0,
                    "last_seen": q["timestamp"],
                    "sources": set()
                }
            
            query_stats[query_text]["count"] += 1
            query_stats[query_text]["total_clicks"] += q.get("click_count", 0)
            
            if q.get("timestamp") > query_stats[query_text]["last_seen"]:
                query_stats[query_text]["last_seen"] = q["timestamp"]
            
            if q.get("sources_searched"):
                query_stats[query_text]["sources"].update(q["sources_searched"])
        
        # Calculate popularity score
        popular = []
        for query_text, stats in query_stats.items():
            stats["sources"] = list(stats["sources"])
            stats["popularity_score"] = stats["count"] * (1 + stats["total_clicks"] / 10)
            popular.append(stats)
        
        # Sort by popularity
        popular.sort(key=lambda x: x["popularity_score"], reverse=True)
        
        return popular[:limit]
    
    def update_query_click(
        self,
        query: str,
        result_id: str,
        user_id: Optional[str] = None
    ):
        """Update click information when user clicks a result"""
        query_vector = self._embed(query)
        
        filter_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=self.tenant_id)
            )
        ]
        
        if user_id:
            filter_conditions.append(
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            )
        
        filter_condition = Filter(must=filter_conditions)
        
        nearest_query = NearestQuery(nearest=query_vector)
        results = self.qdrant.query_points(
            collection_name=self.MEMORY_COLLECTION_NAME,
            query=nearest_query,
            query_filter=filter_condition,
            limit=1
        )
        
        if results.points:
            point = results.points[0]
            current_payload = dict(point.payload) if point.payload else {}
            
            clicked = current_payload.get("results_clicked", [])
            if result_id not in clicked:
                clicked.append(result_id)
                current_payload["results_clicked"] = clicked
                current_payload["click_count"] = len(clicked)
                
                self.qdrant.set_payload(
                    collection_name=self.MEMORY_COLLECTION_NAME,
                    payload=current_payload,
                    points=[point.id]
                )

