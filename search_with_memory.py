"""
Example integration of memory feature with search engine.
This shows how to use the memory module in your search API/endpoint.
"""
from typing import List, Dict, Optional
from memory import (
    save_query,
    get_similar_queries,
    get_query_history,
    get_popular_queries,
    update_query_click
)


def search_with_memory(
    query: str,
    user_id: Optional[str] = None,
    sources: Optional[List[str]] = None
) -> Dict:
    """
    Perform search with memory integration.
    
    This function:
    1. Gets similar past queries for suggestions
    2. Performs the actual search (you'll integrate with your search logic)
    3. Saves the query to memory
    4. Returns results with memory context
    
    Args:
        query: Search query
        user_id: User making the query
        sources: Sources to search (e.g., ['slack', 'gmail', 'drive'])
    
    Returns:
        Dictionary with search results and memory context
    """
    # 1. Get similar past queries for context/suggestions
    similar_queries = get_similar_queries(
        query=query,
        limit=3,
        user_id=user_id,
        min_score=0.7
    )
    
    # 2. Get user's recent query history
    recent_history = get_query_history(
        user_id=user_id,
        limit=5
    )
    
    # 3. Perform actual search (integrate with your search logic here)
    # This is a placeholder - replace with your actual search implementation
    search_results = perform_search(query, sources)
    
    # 4. Save query to memory
    save_query(
        query=query,
        user_id=user_id,
        sources_searched=sources or [],
        result_count=len(search_results.get("results", [])),
        metadata={
            "query_length": len(query),
            "has_results": len(search_results.get("results", [])) > 0
        }
    )
    
    # 5. Return results with memory context
    return {
        "query": query,
        "results": search_results.get("results", []),
        "total_results": len(search_results.get("results", [])),
        "memory": {
            "similar_queries": similar_queries,
            "recent_history": recent_history,
            "suggestions": [sq["query"] for sq in similar_queries[:3]]
        }
    }


def perform_search(query: str, sources: Optional[List[str]] = None) -> Dict:
    """
    Placeholder for actual search implementation.
    Replace this with your actual search logic that queries:
    - Slack
    - Gmail
    - Drive
    - GCal
    - DevRev
    - Alpha
    - etc.
    """
    # TODO: Implement actual search across all sources
    return {
        "results": [
            {
                "id": "result1",
                "title": "Example Result",
                "content": "This is a placeholder result",
                "source": "slack",
                "url": "https://example.com"
            }
        ]
    }


def handle_result_click(
    query: str,
    result_id: str,
    user_id: Optional[str] = None
):
    """
    Call this when a user clicks on a search result.
    This updates the memory to track which results were useful.
    """
    update_query_click(
        query=query,
        result_id=result_id,
        user_id=user_id
    )


# Example API endpoint structure (Flask/FastAPI)
"""
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/api/search', methods=['POST'])
def search_endpoint():
    data = request.json
    query = data.get('query')
    user_id = data.get('user_id')
    sources = data.get('sources', [])
    
    results = search_with_memory(query, user_id, sources)
    return jsonify(results)

@app.route('/api/search/click', methods=['POST'])
def click_endpoint():
    data = request.json
    handle_result_click(
        query=data.get('query'),
        result_id=data.get('result_id'),
        user_id=data.get('user_id')
    )
    return jsonify({"status": "ok"})

@app.route('/api/search/history', methods=['GET'])
def history_endpoint():
    user_id = request.args.get('user_id')
    limit = int(request.args.get('limit', 20))
    history = get_query_history(user_id=user_id, limit=limit)
    return jsonify({"history": history})

@app.route('/api/search/popular', methods=['GET'])
def popular_endpoint():
    limit = int(request.args.get('limit', 10))
    days = int(request.args.get('days', 7))
    popular = get_popular_queries(limit=limit, days_back=days)
    return jsonify({"popular": popular})
"""

