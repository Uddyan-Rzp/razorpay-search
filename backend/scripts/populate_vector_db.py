"""
Script to populate vector database with sample data
Run this after setting up your vector DB and embedding service
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import EmbeddingService, VectorDBService


# Sample documents to populate
SAMPLE_DOCUMENTS = [
    {
        "id": "doc_1",
        "title": "OAuth2 implementation discussion",
        "snippet": "We discussed implementing OAuth2 in our microservices architecture. The team agreed on using JWT tokens for authentication. We'll use refresh tokens for long-lived sessions and implement proper token rotation.",
        "source": "slack",
        "perma_link": "https://razorpay.slack.com/archives/C123/p456",
        "metadata": {
            "author": "@john.doe",
            "date": "2024-01-15",
            "channel": "#engineering"
        }
    },
    {
        "id": "doc_2",
        "title": "Issue #123: OAuth2 implementation guide",
        "snippet": "This issue tracks the implementation of OAuth2 authentication in our API service. See the attached PR for details. Key requirements: support for authorization code flow, PKCE for mobile apps, and token introspection.",
        "source": "github",
        "perma_link": "https://github.com/razorpay/api-service/issues/123",
        "metadata": {
            "author": "@jane.smith",
            "date": "2024-01-14",
            "repo": "razorpay/api-service"
        }
    },
    {
        "id": "doc_3",
        "title": "OAuth2 best practices",
        "snippet": "Here are some best practices we should follow when implementing OAuth2: 1. Always use HTTPS, 2. Implement token refresh, 3. Use short-lived access tokens, 4. Store tokens securely, 5. Implement proper error handling.",
        "source": "slack",
        "perma_link": "https://razorpay.slack.com/archives/C0LM7MQA2/p1765953034059499",
        "metadata": {
            "author": "@alice.wonder",
            "date": "2024-01-13",
            "channel": "#security"
        }
    },
    {
        "id": "doc_4",
        "title": "API rate limiting strategy",
        "snippet": "We need to implement rate limiting for our public API. Options: token bucket algorithm, sliding window, or fixed window. Recommendation: use Redis with sliding window for distributed systems.",
        "source": "slack",
        "perma_link": "https://razorpay.slack.com/archives/C789/p012",
        "metadata": {
            "author": "@bob.dev",
            "date": "2024-01-12",
            "channel": "#engineering"
        }
    },
    {
        "id": "doc_5",
        "title": "PR #456: Add rate limiting middleware",
        "snippet": "This PR adds rate limiting middleware using Redis. Supports per-user and per-IP rate limits. Configurable limits via environment variables. Includes comprehensive tests.",
        "source": "github",
        "perma_link": "https://github.com/razorpay/api-service/pull/456",
        "metadata": {
            "author": "@charlie.code",
            "date": "2024-01-11",
            "repo": "razorpay/api-service"
        }
    },
]


async def populate_database():
    """Populate vector database with sample documents"""
    try:
        print("Initializing services...")
        embedding_service = EmbeddingService()
        vector_db = VectorDBService()
        print("✓ Services initialized\n")
        
        print(f"Processing {len(SAMPLE_DOCUMENTS)} documents...")
        vectors_to_upsert = []
        
        for doc in SAMPLE_DOCUMENTS:
            # Create text for embedding (title + snippet)
            text_to_embed = f"{doc['title']} {doc['snippet']}"
            
            # Generate embedding
            print(f"  Generating embedding for: {doc['title']}")
            embedding = await embedding_service.get_embedding(text_to_embed)
            
            # Prepare vector data
            vector_data = {
                "id": doc["id"],
                "values": embedding,
                "metadata": {
                    "title": doc["title"],
                    "snippet": doc["snippet"],
                    "source": doc["source"],
                    "perma_link": doc["perma_link"],
                    **doc["metadata"]
                }
            }
            
            vectors_to_upsert.append(vector_data)
        
        # Upsert to vector database
        print(f"\nUploading {len(vectors_to_upsert)} vectors to database...")
        await vector_db.upsert(vectors_to_upsert)
        print("✓ Successfully populated vector database!")
        
        # Verify by doing a test search
        print("\nTesting search functionality...")
        test_query = "OAuth2"
        test_embedding = await embedding_service.get_embedding(test_query)
        results = await vector_db.search(test_embedding, top_k=3)
        
        print(f"✓ Test search returned {len(results)} results")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.get('title')} (score: {result.get('score', 0):.3f})")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nMake sure you have:")
        print("1. Set up your .env file with API keys")
        print("2. Installed all dependencies: pip install -r requirements.txt")
        print("3. Created your vector database index")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(populate_database())

