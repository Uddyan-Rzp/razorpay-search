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
from services import LLMService, EmbeddingService, VectorDBService
from config import Config

app = FastAPI(title="RazorSearch API", version="1.0.0")

# Initialize services - these are required for the application to work
llm_service = None
embedding_service = None
vector_db_service = None

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


class SearchResult(BaseModel):
    id: str
    source: str  # 'slack' or 'github'
    title: str
    snippet: str
    perma_link: str
    metadata: dict


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    enriched_query: Optional[str] = None
    cache_hit: Optional[bool] = False


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
    
    # Step 5: Convert to SearchResult format
    results = [
        SearchResult(
            id=result.get("id", ""),
            source=result.get("source", ""),
            title=result.get("title", ""),
            snippet=result.get("snippet", ""),
            perma_link=result.get("perma_link", ""),
            metadata={
                **result.get("metadata", {}),
                "score": result.get("score", 0.0)
            }
        )
        for result in vector_results
    ]
    
    return SearchResponse(
        results=results,
        total=len(results),
        enriched_query=enriched_query,
        cache_hit=False
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

