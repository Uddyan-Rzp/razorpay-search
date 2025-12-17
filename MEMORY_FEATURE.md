# Memory Feature for Search Engine

This memory feature remembers past queries and provides intelligent suggestions and context for your internal search engine.

## Features

1. **Query Storage**: Automatically saves all search queries with metadata
2. **Similar Query Retrieval**: Finds similar past queries using vector embeddings
3. **Query History**: Retrieves recent query history for users
4. **Popular Queries**: Identifies trending/popular queries based on frequency and clicks
5. **Click Tracking**: Tracks which results users click on to improve relevance

## Setup

The memory feature uses the same Qdrant and Azure OpenAI setup as your ingestion script. Make sure you have:

- Qdrant running on `http://localhost:6333`
- Environment variables set in `.env`:
  - `OPENAI_API_KEY`
  - `ORG_NAME` (used as tenant_id)

## Quick Start

### 1. Basic Usage

```python
from memory import save_query, get_similar_queries, get_query_history

# Save a query
save_query(
    query="how to deploy to production",
    user_id="user123",
    sources_searched=["slack", "github"],
    result_count=15
)

# Get similar queries
similar = get_similar_queries("deploy production", limit=5)
print(similar)

# Get query history
history = get_query_history(user_id="user123", limit=10)
print(history)
```

### 2. Integration with Search

See `search_with_memory.py` for a complete example of how to integrate memory with your search engine.

```python
from search_with_memory import search_with_memory

# Perform search with memory
results = search_with_memory(
    query="deployment process",
    user_id="user123",
    sources=["slack", "gmail", "drive"]
)

# Results include:
# - search results
# - similar past queries
# - recent query history
# - suggestions
```

### 3. Track Result Clicks

When a user clicks on a search result, update the memory:

```python
from search_with_memory import handle_result_click

handle_result_click(
    query="deployment process",
    result_id="result_abc123",
    user_id="user123"
)
```

## API Functions

### `save_query(query, user_id=None, results_clicked=None, sources_searched=None, result_count=0, metadata=None)`

Saves a query to memory.

**Parameters:**
- `query` (str): The search query text
- `user_id` (str, optional): ID of the user who made the query
- `results_clicked` (List[str], optional): List of result IDs that were clicked
- `sources_searched` (List[str], optional): Sources searched (e.g., ['slack', 'gmail'])
- `result_count` (int): Number of results returned
- `metadata` (Dict, optional): Additional metadata

**Returns:** Query ID

### `get_similar_queries(query, limit=5, user_id=None, min_score=0.7)`

Finds similar past queries using vector similarity.

**Parameters:**
- `query` (str): Current query
- `limit` (int): Max number of results
- `user_id` (str, optional): Filter by user
- `min_score` (float): Minimum similarity score (0-1)

**Returns:** List of similar queries with metadata

### `get_query_history(user_id=None, limit=20, days_back=None)`

Gets recent query history.

**Parameters:**
- `user_id` (str, optional): Filter by user
- `limit` (int): Max number of queries
- `days_back` (int, optional): Number of days to look back

**Returns:** List of queries sorted by timestamp (newest first)

### `get_popular_queries(limit=10, days_back=7)`

Gets most popular queries based on frequency and clicks.

**Parameters:**
- `limit` (int): Max number of queries
- `days_back` (int): Number of days to look back

**Returns:** List of popular queries with stats

### `update_query_click(query, result_id, user_id=None)`

Updates click information when a user clicks a result.

**Parameters:**
- `query` (str): Original query
- `result_id` (str): ID of clicked result
- `user_id` (str, optional): User ID

## Use Cases

### 1. Query Autocomplete/Suggestions

```python
# Get suggestions as user types
def get_autocomplete_suggestions(partial_query, user_id=None):
    similar = get_similar_queries(partial_query, limit=5, user_id=user_id)
    return [sq["query"] for sq in similar]
```

### 2. "You searched for..." Feature

```python
# Show user their recent searches
recent = get_query_history(user_id="user123", limit=10)
# Display in UI: "You recently searched for..."
```

### 3. Trending Searches

```python
# Show popular searches across the organization
popular = get_popular_queries(limit=10, days_back=7)
# Display: "Trending searches this week"
```

### 4. Contextual Search Results

```python
# Enhance search results with similar past queries
similar = get_similar_queries(current_query, limit=3)
# Show: "People also searched for: ..."
```

## Data Structure

Queries are stored in Qdrant with the following structure:

```json
{
  "query": "how to deploy to production",
  "tenant_id": "your_org",
  "timestamp": "2024-01-15T10:30:00",
  "user_id": "user123",
  "result_count": 15,
  "click_count": 3,
  "results_clicked": ["result1", "result2", "result3"],
  "sources_searched": ["slack", "github"],
  "type": "query_memory"
}
```

## Collection Management

The memory feature automatically creates a Qdrant collection named `query_memory` on first use. The collection uses:
- **Vector size**: Determined by your embedding model
- **Distance metric**: Cosine similarity
- **Collection name**: `query_memory`

## Privacy & ACLs

The memory system respects tenant isolation:
- All queries are tagged with `tenant_id`
- Queries are filtered by `tenant_id` in all retrieval functions
- User-specific queries can be filtered by `user_id`

Make sure to:
- Only save queries that the user has permission to search
- Filter results based on user's access permissions
- Respect ACLs when displaying query history

## Performance Tips

1. **Batch Operations**: For bulk imports, consider batching multiple queries
2. **Caching**: Cache popular queries and suggestions
3. **Pagination**: Use `limit` parameters to avoid loading too much data
4. **Indexing**: Qdrant automatically indexes vectors for fast similarity search

## Example Integration (Flask)

```python
from flask import Flask, request, jsonify
from memory import save_query, get_similar_queries, get_query_history
from search_with_memory import search_with_memory

app = Flask(__name__)

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json
    results = search_with_memory(
        query=data['query'],
        user_id=data.get('user_id'),
        sources=data.get('sources', [])
    )
    return jsonify(results)

@app.route('/api/search/suggestions', methods=['GET'])
def suggestions():
    query = request.args.get('q', '')
    user_id = request.args.get('user_id')
    similar = get_similar_queries(query, limit=5, user_id=user_id)
    return jsonify({"suggestions": [s["query"] for s in similar]})
```

## Testing

Run the memory module directly to test:

```bash
python memory.py
```

This will run example usage code and demonstrate the functionality.

