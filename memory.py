import os
import time
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, NearestQuery
from openai import AzureOpenAI

# ---------------- CONFIG ----------------
load_dotenv()
OPENAI_API_KEY = os.environ["EMBEDDING_AZURE_API_KEY"]
TENANT_ID = os.environ.get("ORG_NAME", "default")

MEMORY_COLLECTION_NAME = "query_memory"

client = AzureOpenAI(
    api_key=OPENAI_API_KEY,
    azure_endpoint="https://fy26-hackon-q3.openai.azure.com/",
    api_version="2023-05-15"
)

qdrant = QdrantClient(url="http://localhost:6333")

# ---------------- HELPERS ----------------

def embed(text: str) -> List[float]:
    """Generate embedding for text using Azure OpenAI."""
    res = client.embeddings.create(
        model="fy26-hackon-q3-emb",
        input=text
    )
    return res.data[0].embedding

def ensure_collection():
    """Ensure the memory collection exists in Qdrant."""
    try:
        collections = qdrant.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if MEMORY_COLLECTION_NAME not in collection_names:
            # Get vector size from embedding
            sample_embedding = embed("sample")
            vector_size = len(sample_embedding)
            
            qdrant.create_collection(
                collection_name=MEMORY_COLLECTION_NAME,
                vectors_config={
                    "size": vector_size,
                    "distance": "Cosine"
                }
            )
            print(f"Created collection: {MEMORY_COLLECTION_NAME}")
    except Exception as e:
        print(f"Error ensuring collection: {e}")

# ---------------- MEMORY FUNCTIONS ----------------

def save_query(
    query: str,
    user_id: Optional[str] = None,
    results_clicked: Optional[List[str]] = None,
    sources_searched: Optional[List[str]] = None,
    result_count: int = 0,
    metadata: Optional[Dict] = None
):
    """
    Save a query to memory with associated metadata.
    
    Args:
        query: The search query text
        user_id: ID of the user who made the query
        results_clicked: List of result IDs that were clicked
        sources_searched: List of sources that were searched (e.g., ['slack', 'gmail'])
        result_count: Number of results returned
        metadata: Additional metadata to store
    """
    ensure_collection()
    
    timestamp = datetime.now().isoformat()
    # Use integer timestamp as ID (milliseconds since epoch)
    query_id = int(time.time() * 1000000)  # microseconds for better uniqueness
    
    # Create embedding for the query
    vector = embed(query)
    
    # Build payload
    payload = {
        "query": query,
        "tenant_id": TENANT_ID,
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
    qdrant.upsert(
        collection_name=MEMORY_COLLECTION_NAME,
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
    query: str,
    limit: int = 5,
    user_id: Optional[str] = None,
    min_score: float = 0.7
) -> List[Dict]:
    """
    Retrieve similar past queries using vector similarity search.
    
    Args:
        query: Current query to find similar ones for
        limit: Maximum number of similar queries to return
        user_id: Optional user ID to filter queries by user
        min_score: Minimum similarity score (0-1)
    
    Returns:
        List of similar queries with metadata
    """
    ensure_collection()
    
    query_vector = embed(query)
    
    # Build filter if user_id is provided
    filter_condition = None
    if user_id:
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                ),
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=TENANT_ID)
                )
            ]
        )
    else:
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=TENANT_ID)
                )
            ]
        )
    
    # Search for similar queries using query_points
    nearest_query = NearestQuery(nearest=query_vector)
    results = qdrant.query_points(
        collection_name=MEMORY_COLLECTION_NAME,
        query=nearest_query,
        query_filter=filter_condition,
        limit=limit,
        score_threshold=min_score
    )
    
    similar_queries = []
    for point in results.points:
        similar_queries.append({
            "query": point.payload.get("query", ""),
            "score": point.score,
            "timestamp": point.payload.get("timestamp"),
            "user_id": point.payload.get("user_id"),
            "click_count": point.payload.get("click_count", 0),
            "sources_searched": point.payload.get("sources_searched", []),
            "result_count": point.payload.get("result_count", 0),
            "metadata": {k: v for k, v in point.payload.items() 
                        if k not in ["query", "timestamp", "user_id", "click_count", 
                                    "sources_searched", "result_count", "tenant_id", "type"]}
        })
    
    return similar_queries

def get_query_history(
    user_id: Optional[str] = None,
    limit: int = 20,
    days_back: Optional[int] = None
) -> List[Dict]:
    """
    Get recent query history.
    
    Args:
        user_id: Optional user ID to filter by
        limit: Maximum number of queries to return
        days_back: Optional number of days to look back
    
    Returns:
        List of recent queries sorted by timestamp (newest first)
    """
    ensure_collection()
    
    # Build filter
    filter_conditions = [
        FieldCondition(
            key="tenant_id",
            match=MatchValue(value=TENANT_ID)
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
    
    # Scroll through all matching queries
    # Note: This is a simplified approach. For production, you'd want pagination
    results = qdrant.scroll(
        collection_name=MEMORY_COLLECTION_NAME,
        scroll_filter=filter_condition,
        limit=limit * 2,  # Get more to sort and filter
        with_payload=True,
        with_vectors=False
    )
    
    queries = []
    for point in results[0]:  # results is a tuple (points, next_page_offset)
        payload = point.payload
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
    limit: int = 10,
    days_back: Optional[int] = 7
) -> List[Dict]:
    """
    Get most popular queries based on click count and frequency.
    
    Args:
        limit: Maximum number of queries to return
        days_back: Number of days to look back (default: 7)
    
    Returns:
        List of popular queries with aggregated stats
    """
    ensure_collection()
    
    # Get recent queries
    recent_queries = get_query_history(limit=1000, days_back=days_back)
    
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
    
    # Convert sets to lists and calculate popularity score
    popular = []
    for query_text, stats in query_stats.items():
        stats["sources"] = list(stats["sources"])
        # Simple popularity score: count * (1 + clicks/10)
        stats["popularity_score"] = stats["count"] * (1 + stats["total_clicks"] / 10)
        popular.append(stats)
    
    # Sort by popularity score
    popular.sort(key=lambda x: x["popularity_score"], reverse=True)
    
    return popular[:limit]

def update_query_click(
    query: str,
    result_id: str,
    user_id: Optional[str] = None
):
    """
    Update a query's click information when a user clicks on a result.
    This helps improve the memory system by tracking which results were useful.
    
    Args:
        query: The original query
        result_id: ID of the result that was clicked
        user_id: Optional user ID
    """
    ensure_collection()
    
    query_vector = embed(query)
    
    # Find the most recent matching query
    filter_conditions = [
        FieldCondition(
            key="tenant_id",
            match=MatchValue(value=TENANT_ID)
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
    results = qdrant.query_points(
        collection_name=MEMORY_COLLECTION_NAME,
        query=nearest_query,
        query_filter=filter_condition,
        limit=1
    )
    
    if results.points:
        point = results.points[0]
        # Get current payload
        current_payload = {}
        if hasattr(point, 'payload') and point.payload:
            current_payload = dict(point.payload)
        
        # Update click information
        clicked = current_payload.get("results_clicked", [])
        if result_id not in clicked:
            clicked.append(result_id)
            current_payload["results_clicked"] = clicked
            current_payload["click_count"] = len(clicked)
            
            # Update the point
            qdrant.set_payload(
                collection_name=MEMORY_COLLECTION_NAME,
                payload=current_payload,
                points=[point.id]
            )

# ---------------- EXAMPLE USAGE ----------------

if __name__ == "__main__":
    # Example: Save a query
    query_id = save_query(
        query="how to deploy to production",
        user_id="user123",
        sources_searched=["slack", "github"],
        result_count=15,
        results_clicked=["result1", "result2"]
    )
    print(f"Saved query with ID: {query_id}")
    
    # Example: Get similar queries
    similar = get_similar_queries("deploy production", limit=3)
    print(f"\nSimilar queries: {similar}")
    
    # Example: Get query history
    history = get_query_history(user_id="user123", limit=5)
    print(f"\nQuery history: {history}")
    
    # Example: Get popular queries
    popular = get_popular_queries(limit=5)
    print(f"\nPopular queries: {popular}")

