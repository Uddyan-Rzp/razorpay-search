"""
Vector Database Service for storing and retrieving embeddings
"""
import os
from typing import List, Dict, Optional
from config import Config


class VectorDBService:
    """Service for interacting with vector databases"""
    
    def __init__(self):
        self.provider = Config.VECTOR_DB_PROVIDER
        if self.provider != "qdrant":
            raise ValueError(f"Unsupported vector DB provider: {self.provider}. Only 'qdrant' is supported.")
        self.collection_name = Config.QDRANT_COLLECTION_NAME
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the vector DB client based on provider"""
        if self.provider == "qdrant":
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams, PointStruct
                
                # Initialize Qdrant client (server or cloud mode)
                if not Config.QDRANT_URL:
                    raise ValueError("QDRANT_URL is required. Set it in .env file (e.g., http://localhost:6333 for local Docker server)")
                
                if Config.QDRANT_API_KEY:
                    # Cloud mode: URL + API key
                    self.client = QdrantClient(
                        url=Config.QDRANT_URL,
                        api_key=Config.QDRANT_API_KEY
                    )
                    print(f"Connected to Qdrant Cloud: {Config.QDRANT_URL}")
                else:
                    # Local server mode: URL without API key (e.g., http://localhost:6333)
                    self.client = QdrantClient(url=Config.QDRANT_URL)
                    print(f"Connected to Qdrant server: {Config.QDRANT_URL}")
                
                # Get or create collection
                collections = self.client.get_collections().collections
                collection_exists = any(c.name == self.collection_name for c in collections)
                
                if not collection_exists:
                    # Create collection if it doesn't exist
                    dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(
                            size=dimension,
                            distance=Distance.COSINE
                        )
                    )
                    print(f"Created Qdrant collection: {self.collection_name}")
                else:
                    print(f"Using existing Qdrant collection: {self.collection_name}")
                
                self.PointStruct = PointStruct
                
            except ImportError:
                raise ImportError("qdrant-client package not installed. Run: pip install qdrant-client")
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict] = None,
        include_metadata: bool = True
    ) -> List[Dict]:
        """
        Search for similar vectors in the database
        """
        top_k = min(top_k, Config.MAX_SEARCH_RESULTS)
        
        try:
            # Build filter if provided
            from qdrant_client.models import Filter, FieldCondition, MatchAny
            
            query_filter = None
            if filters and "sources" in filters:
                # MatchAny expects a list of values
                source_list = filters["sources"] if isinstance(filters["sources"], list) else [filters["sources"]]
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="source",
                            match=MatchAny(any=source_list)
                        )
                    ]
                )
            
            # Search Qdrant using query_points
            from qdrant_client.models import NearestQuery
            
            # NearestQuery expects the vector directly in the 'nearest' field
            query = NearestQuery(
                nearest=query_vector
            )
            
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query,
                limit=top_k,
                query_filter=query_filter,
                score_threshold=Config.MIN_SIMILARITY_SCORE,
                with_payload=True
            )
            
            # Format results
            formatted_results = []
            for result in response.points:
                payload = result.payload or {}
                # Use original_id if available, otherwise use the integer ID as string
                result_id = payload.get("original_id", str(result.id))
                # Get score from result (Qdrant returns score in the result)
                score = getattr(result, 'score', 0.0)
                formatted_results.append({
                    "id": result_id,
                    "score": score,
                    "title": payload.get("title", ""),
                    "snippet": payload.get("snippet", ""),
                    "source": payload.get("source", ""),
                    "perma_link": payload.get("perma_link", ""),
                    "metadata": {
                        k: v for k, v in payload.items()
                        if k not in ["title", "snippet", "source", "perma_link", "original_id"]
                    }
                })
            
            return formatted_results
        
        except Exception as e:
            print(f"Vector DB search failed: {e}")
            return []
    
    async def upsert(self, vectors: List[Dict]):
        """
        Insert or update vectors in the database
        Format: [{"id": "doc1", "values": [0.1, 0.2, ...], "metadata": {...}}, ...]
        """
        try:
            import hashlib
            # Convert vectors to Qdrant PointStruct format
            points = []
            for vector_data in vectors:
                # Convert string ID to integer (Qdrant requires int or UUID)
                point_id = vector_data["id"]
                if isinstance(point_id, str):
                    # Generate deterministic integer from string using hash
                    # Use first 8 bytes of hash to create a positive integer
                    hash_obj = hashlib.md5(point_id.encode())
                    point_id = int(hash_obj.hexdigest()[:15], 16)  # Use first 15 hex chars (max safe int)
                
                point = self.PointStruct(
                    id=point_id,
                    vector=vector_data["values"],
                    payload={
                        **vector_data["metadata"],
                        "title": vector_data["metadata"].get("title", ""),
                        "snippet": vector_data["metadata"].get("snippet", ""),
                        "source": vector_data["metadata"].get("source", ""),
                        "perma_link": vector_data["metadata"].get("perma_link", ""),
                        "original_id": vector_data["id"]  # Store original string ID in payload
                    }
                )
                points.append(point)
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        except Exception as e:
            print(f"Vector DB upsert failed: {e}")
            raise

