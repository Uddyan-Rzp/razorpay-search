"""
RazorSearch Backend API
A simple FastAPI backend for the search engine
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os

# Import required services
from services import LLMService, EmbeddingService, VectorDBService, MemoryService
from config import Config

app = FastAPI(title="RazorSearch API", version="1.0.0")

# Initialize services - these are required for the application to work
llm_service = None
embedding_service = None
vector_db_service = None
memory_service = None

try:
    embedding_service = EmbeddingService()
    print("✓ Embedding Service initialized")
except Exception as e:
    print(f"✗ Embedding Service initialization failed: {e}")
    print("ERROR: Embedding service is required. Please check your configuration.")
    raise

try:
    vector_db_service = VectorDBService()
    print("✓ Vector DB Service initialized")
except Exception as e:
    print(f"✗ Vector DB Service initialization failed: {e}")
    print("ERROR: Vector DB service is required. Please check your configuration.")
    raise

try:
    llm_service = LLMService()
    print("✓ LLM Service initialized")
except Exception as e:
    print(f"⚠ LLM Service initialization failed: {e}")
    print("WARNING: LLM service is optional. Query enrichment will be disabled.")

try:
    memory_service = MemoryService()
    print("✓ Memory Service initialized")
except Exception as e:
    print(f"⚠ Memory Service initialization failed: {e}")
    print("WARNING: Memory service is optional. Query memory features will be disabled.")

# CORS middleware to allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class SearchRequest(BaseModel):
    query: str
    filters: Optional[dict] = None
    session_id: Optional[str] = None
    include_context: Optional[bool] = False
    user_id: Optional[str] = None  # For memory features


class SearchResult(BaseModel):
    id: str
    source: str  # 'slack' or 'github'
    title: str
    snippet: str
    content: str  # Full content
    summary: Optional[str] = None  # LLM-generated summary
    perma_link: str
    metadata: dict


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    enriched_query: Optional[str] = None
    cache_hit: Optional[bool] = False
    memory: Optional[dict] = None  # Memory features: suggestions, history, etc.


@app.post("/api/v1/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search endpoint that accepts a query and returns results from vector database.
    Uses LLM for query enrichment (optional) and Vector DB for semantic search (required).
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Validate required services
    if not embedding_service:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not available. Please check your configuration."
        )
    
    if not vector_db_service:
        raise HTTPException(
            status_code=503,
            detail="Vector database service is not available. Please check your configuration."
        )

    original_query = request.query.strip()
    enriched_query = original_query
    search_query = original_query

    # Step 1: Enrich query with LLM (optional)
    if llm_service:
        try:
            enriched_query = await llm_service.enrich_query(original_query)
            search_query = enriched_query
            print(f"Query enriched: '{original_query}' -> '{enriched_query}'")
        except Exception as e:
            print(f"⚠ Query enrichment failed (using original query): {type(e).__name__}: {e}")
            enriched_query = original_query
            search_query = original_query

    # Step 2: Generate embedding for the search query
    try:
        query_embedding = await embedding_service.get_embedding(search_query)
    except Exception as e:
        error_msg = str(e)
        if "API key" in error_msg or "authentication" in error_msg.lower():
            detail = f"Embedding service authentication failed. Please check your API key in .env file. Error: {error_msg}"
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            detail = f"Embedding service connection failed. Please check your internet connection and API key. Error: {error_msg}"
        else:
            detail = f"Failed to generate embedding: {error_msg}"
        
        print(f"✗ Embedding generation failed: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=detail
        )
    
    # Step 3: Extract filters from request
    filters = None
    if request.filters:
        filters = request.filters
    
    # Step 4: Search vector database
    try:
        vector_results = await vector_db_service.search(
            query_vector=query_embedding,
            top_k=Config.MAX_SEARCH_RESULTS,
            filters=filters
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Vector database search failed: {str(e)}"
        )
    
    # Step 5: Convert to SearchResult format and generate summaries
    results = []
    for result in vector_results:
        # Generate LLM summary for each result (if LLM service is available)
        summary = None
        if llm_service:
            try:
                summary = await llm_service.summarize_content(
                    content=result.get("content", ""),
                    source=result.get("source", ""),
                    query=original_query
                )
            except Exception as e:
                print(f"⚠️  Summary generation failed for result {result.get('id', '')}: {e}")
        
        results.append(
            SearchResult(
                id=result.get("id", ""),
                source=result.get("source", ""),
                title=result.get("title", ""),
                snippet=result.get("snippet", ""),
                content=result.get("content", ""),
                summary=summary,
                perma_link=result.get("perma_link", ""),
                metadata={
                    **result.get("metadata", {}),
                    "score": result.get("score", 0.0)
                }
            )
        )
    
    # Step 6: Memory features (if available)
    memory_data = None
    if memory_service:
        try:
            # Get similar queries for suggestions
            similar_queries = memory_service.get_similar_queries(
                query=original_query,
                limit=3,
                user_id=request.user_id,
                min_score=0.7
            )
            
            # Get recent history
            recent_history = memory_service.get_query_history(
                user_id=request.user_id,
                limit=5
            )
            
            # Extract sources from filters if available
            sources_searched = []
            if request.filters and "sources" in request.filters:
                sources_searched = request.filters["sources"] if isinstance(request.filters["sources"], list) else [request.filters["sources"]]
            
            # Save query to memory
            memory_service.save_query(
                query=original_query,
                user_id=request.user_id,
                sources_searched=sources_searched,
                result_count=len(results)
            )
            
            memory_data = {
                "similar_queries": similar_queries,
                "recent_history": recent_history,
                "suggestions": [sq["query"] for sq in similar_queries[:3]]
            }
        except Exception as e:
            print(f"⚠ Memory features failed: {e}")
            memory_data = None
    
    return SearchResponse(
        results=results,
        total=len(results),
        enriched_query=enriched_query,
        cache_hit=False,
        memory=memory_data
    )


# Memory endpoints
@app.get("/api/v1/memory/suggestions")
async def get_suggestions(q: str = "", user_id: Optional[str] = None):
    """Get query suggestions for autocomplete"""
    if not memory_service:
        return {"suggestions": []}
    
    if not q or len(q) < 2:
        return {"suggestions": []}
    
    try:
        similar = memory_service.get_similar_queries(
            query=q,
            limit=5,
            user_id=user_id,
            min_score=0.6
        )
        return {"suggestions": [s["query"] for s in similar]}
    except Exception as e:
        print(f"⚠ Suggestions failed: {e}")
        return {"suggestions": []}


@app.get("/api/v1/memory/history")
async def get_history(user_id: Optional[str] = None, limit: int = 20):
    """Get user's query history"""
    if not memory_service:
        return {"history": []}
    
    try:
        history = memory_service.get_query_history(user_id=user_id, limit=limit)
        return {"history": history}
    except Exception as e:
        print(f"⚠ History failed: {e}")
        return {"history": []}


@app.get("/api/v1/memory/popular")
async def get_popular(limit: int = 10, days: int = 7):
    """Get popular/trending queries"""
    if not memory_service:
        return {"popular": []}
    
    try:
        popular = memory_service.get_popular_queries(limit=limit, days_back=days)
        return {"popular": popular}
    except Exception as e:
        print(f"⚠ Popular queries failed: {e}")
        return {"popular": []}


class ClickRequest(BaseModel):
    query: str
    result_id: str
    user_id: Optional[str] = None


@app.post("/api/v1/memory/click")
async def track_click(request: ClickRequest):
    """Track when user clicks on a search result"""
    if not memory_service:
        return {"status": "ok", "message": "Memory service not available"}
    
    try:
        memory_service.update_query_click(
            query=request.query,
            result_id=request.result_id,
            user_id=request.user_id
        )
        return {"status": "ok", "message": "Click tracked"}
    except Exception as e:
        print(f"⚠ Click tracking failed: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

