"""
Simple test script to demonstrate the memory feature.
Run this to see how the memory system works.
"""
from memory import (
    save_query,
    get_similar_queries,
    get_query_history,
    get_popular_queries,
    update_query_click
)

def demo_memory():
    print("=" * 60)
    print("Memory Feature Demo")
    print("=" * 60)
    
    # 1. Save some sample queries
    print("\n1. Saving sample queries...")
    queries_to_save = [
        {
            "query": "how to deploy to production",
            "user_id": "alice",
            "sources_searched": ["slack", "github"],
            "result_count": 12
        },
        {
            "query": "production deployment process",
            "user_id": "bob",
            "sources_searched": ["slack", "gmail"],
            "result_count": 8
        },
        {
            "query": "how to fix authentication error",
            "user_id": "alice",
            "sources_searched": ["slack", "github"],
            "result_count": 15
        },
        {
            "query": "authentication issues",
            "user_id": "charlie",
            "sources_searched": ["slack"],
            "result_count": 5
        },
        {
            "query": "deploy production environment",
            "user_id": "alice",
            "sources_searched": ["github", "drive"],
            "result_count": 10,
            "results_clicked": ["result1", "result2"]
        }
    ]
    
    for q in queries_to_save:
        query_id = save_query(**q)
        print(f"  ✓ Saved: '{q['query']}' (ID: {query_id})")
    
    # 2. Find similar queries
    print("\n2. Finding similar queries to 'deploy to production'...")
    similar = get_similar_queries("deploy to production", limit=3)
    for sq in similar:
        print(f"  - '{sq['query']}' (similarity: {sq['score']:.3f}, user: {sq.get('user_id', 'N/A')})")
    
    # 3. Get query history for a user
    print("\n3. Getting query history for user 'alice'...")
    history = get_query_history(user_id="alice", limit=5)
    for h in history:
        print(f"  - '{h['query']}' at {h.get('timestamp', 'N/A')}")
    
    # 4. Get popular queries
    print("\n4. Getting popular queries...")
    popular = get_popular_queries(limit=5)
    for p in popular:
        print(f"  - '{p['query']}' (searched {p['count']} times, {p['total_clicks']} clicks)")
    
    # 5. Update click information
    print("\n5. Simulating a click on a result...")
    update_query_click(
        query="how to deploy to production",
        result_id="result_new_click",
        user_id="alice"
    )
    print("  ✓ Updated click information")
    
    # 6. Get similar queries again (should reflect the click)
    print("\n6. Getting similar queries again...")
    similar_after = get_similar_queries("deploy production", limit=2)
    for sq in similar_after:
        clicks = sq.get('click_count', 0)
        print(f"  - '{sq['query']}' (similarity: {sq['score']:.3f}, clicks: {clicks})")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        demo_memory()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure:")
        print("1. Qdrant is running on http://localhost:6333")
        print("2. Environment variables are set (.env file)")
        print("3. Azure OpenAI credentials are configured")

