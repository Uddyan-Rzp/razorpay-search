import os
import time
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv
from datetime import datetime, timedelta
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from openai import AzureOpenAI

# ---------------- CONFIG ----------------
load_dotenv()

# Validate required environment variables
if "SLACK_TOKEN" not in os.environ:
    raise ValueError(
        "SLACK_TOKEN not found in environment variables!\n"
        "Add it to your .env file:\n"
        "SLACK_TOKEN=xoxb-your-token-here"
    )

SLACK_TOKEN = os.environ["SLACK_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ORG = os.environ.get("ORG_NAME", "organization")

COLLECTION_NAME = "documents"
TENANT_ID = ORG

VECTOR_SIZE = int(os.environ["VECTOR_SIZE"])  # text-embedding-3-small

client = AzureOpenAI(
    api_key=OPENAI_API_KEY,
    azure_endpoint="https://fy26-hackon-q3.openai.azure.com/",
    api_version="2024-02-01"
)

SLACK_HEADERS = {
    "Authorization": f"Bearer {SLACK_TOKEN}",
    "Content-Type": "application/json"
}

qdrant = QdrantClient(url="http://localhost:6333")

# ---------------- HELPERS ----------------

def slack_get(endpoint: str, params: Optional[Dict] = None):
    """Make a GET request to Slack API"""
    url = f"https://slack.com/api/{endpoint}"
    resp = requests.get(url, headers=SLACK_HEADERS, params=params or {})
    resp.raise_for_status()
    time.sleep(1)  # Slack rate limiting
    data = resp.json()
    
    if not data.get("ok"):
        error = data.get('error', 'Unknown error')
        raise Exception(f"Slack API error: {error}")
    
    return data

def test_slack_connection():
    """Test Slack API connection and token validity"""
    try:
        print("Testing Slack API connection...")
        data = slack_get("auth.test")
        print(f"✓ Connected to Slack workspace: {data.get('team', 'Unknown')}")
        print(f"✓ Bot user: {data.get('user', 'Unknown')}")
        return True
    except Exception as e:
        print(f"✗ Slack connection failed: {e}")
        return False

def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in text.
    Rough approximation: 1 token ≈ 4 characters for English text.
    """
    return len(text) // 4

def chunk_text(text: str, max_tokens: int = 6000) -> str:
    """
    Chunk/truncate text to fit within token limit.
    Keeps the most important parts and uses LLM to summarize if too long.
    
    Args:
        text: Text to chunk
        max_tokens: Maximum tokens allowed (default 6000, leaving safe buffer for 8192 limit)
    
    Returns:
        Truncated or summarized text that fits within token limit
    """
    estimated_tokens = estimate_tokens(text)
    
    if estimated_tokens <= max_tokens:
        return text
    
    print(f"⚠️  Text too long ({estimated_tokens} tokens). Summarizing...")
    
    # Calculate how much text we can keep (roughly)
    max_chars = max_tokens * 4
    
    # Try to use LLM to create a concise summary
    try:
        # Take a reasonable portion of the text for summarization
        text_to_summarize = text[:max_chars * 2]  # Give LLM more context
        
        prompt = f"""This Slack conversation is too long for embedding. Create a comprehensive but concise summary that preserves:
- Key technical discussions and solutions
- Important decisions
- Action items and outcomes
- Critical context

Keep it under 1500 words maximum.

Conversation to summarize:
{text_to_summarize}

Concise summary:"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a conversation summarizer. Create comprehensive but concise summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Add note about summarization
        result = f"{summary}\n\n[Note: This conversation was summarized due to length constraints]"
        
        # Double check the result isn't still too long
        if estimate_tokens(result) > max_tokens:
            print(f"⚠️  Summary still too long. Truncating to {max_tokens} tokens.")
            result = result[:max_chars] + "\n\n[Note: Content was summarized and truncated due to length]"
        
        print(f"✓ Summarized to ~{estimate_tokens(result)} tokens")
        return result
        
    except Exception as e:
        print(f"⚠️  Summarization failed: {e}. Using truncation.")
        # Fallback: simple truncation
        truncated = text[:max_chars]
        return f"{truncated}\n\n[Note: Content truncated due to length]"

def embed(text: str) -> List[float]:
    """Generate embedding for text with automatic chunking if needed"""
    # Ensure text fits within token limit
    chunked_text = chunk_text(text)
    
    res = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunked_text
    )
    return res.data[0].embedding

def ensure_collection():
    """Ensure Qdrant collection exists"""
    existing = qdrant.get_collections().collections
    if any(c.name == COLLECTION_NAME for c in existing):
        return

    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE
        )
    )
    print(f"Created collection: {COLLECTION_NAME}")

def str_to_uuid(value: str) -> str:
    """Convert string to UUID"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, value))

def document_exists(doc_id: str) -> bool:
    """
    Check if a document already exists in Qdrant.
    
    Args:
        doc_id: The document ID to check
    
    Returns:
        True if document exists, False otherwise
    """
    try:
        uuid_id = str_to_uuid(doc_id)
        result = qdrant.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[uuid_id]
        )
        return len(result) > 0
    except Exception:
        return False

def upsert_doc(doc_id: str, content: str, metadata: Dict):
    """Upsert document to Qdrant"""
    try:
        vector = embed(content)
        new_id = str_to_uuid(doc_id)
        print(f"Upserting: {new_id}")
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=new_id,
                    vector=vector,
                    payload={
                        "content": content,
                        **metadata
                    }
                )
            ]
        )
    except Exception as e:
        print(f"⚠️  WARNING: Failed to upsert document {doc_id}: {e}")
        print(f"   Skipping this document and continuing...")

def get_user_name(user_id: str, user_cache: Dict) -> str:
    """Get user name from Slack user ID with caching"""
    if user_id in user_cache:
        return user_cache[user_id]
    
    try:
        data = slack_get("users.info", {"user": user_id})
        name = data["user"]["real_name"] or data["user"]["name"]
        user_cache[user_id] = name
        return name
    except Exception:
        return user_id

def get_timestamp_for_days_ago(days: int) -> str:
    """
    Get Unix timestamp for N days ago.
    Slack uses timestamps with decimal (e.g., "1234567890.123456")
    """
    target_date = datetime.now() - timedelta(days=days)
    unix_timestamp = target_date.timestamp()
    return str(unix_timestamp)

# ---------------- LLM FILTERS ----------------

def is_useful_message(message_text: str) -> bool:
    """
    Use LLM to determine if a Slack message contains useful information.
    
    Filters out:
    - Greetings and small talk
    - Jokes and memes
    - Random chatter
    - Simple acknowledgments (thanks, ok, etc.)
    
    Returns:
        True if the message is useful, False otherwise
    """
    try:
        prompt = f"""Evaluate if this Slack message contains useful information for documentation and knowledge base.

Message:
{message_text}

Consider it USEFUL if it contains:
- Technical discussions or solutions
- Important decisions
- Any new technical feature announcements
- Bug reports or troubleshooting
- Feature requests or specifications
- Architecture or design discussions
- Meeting notes or action items
- Links to important resources

Consider it NOT USEFUL if it's:
- Simple greetings (hi, hello, good morning, etc.)
- Jokes, memes, or casual banter
- Random chatter or off-topic
- Simple acknowledgments (thanks, ok, got it, 👍, etc.)
- Out of office or availability messages
- Any event announcements
- Just emoji reactions
- Any bot announcements or messages

Respond with ONLY "USEFUL" or "NOT_USEFUL":"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Slack message evaluator. Respond with only 'USEFUL' or 'NOT_USEFUL'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip().upper()
        print(f"Message usefulness: {result}")
        
        # Check for NOT_USEFUL first (takes precedence)
        if "NOT_USEFUL" in result or "NOT USEFUL" in result:
            return False
        elif "USEFUL" in result:
            return True
        else:
            print(f"Warning: Unclear response from LLM: {result}")
            return False  # For Slack, default to excluding unclear messages
    
    except Exception as e:
        print(f"Warning: Message usefulness check failed: {e}")
        return True  # If check fails, include the message

def refine_message(message_text: str, author: str) -> str:
    """
    Use LLM to refine and clean up the message without making it verbose.
    Removes noise while preserving key information.
    """
    try:
        prompt = f"""Refine this Slack message to be concise and clear while preserving all important information.

Original message by {author}:
{message_text}

Rules:
- Keep technical details, decisions, and action items
- Remove excessive formatting, emojis or repetition
- Fix typos and improve clarity
- Stay concise - do NOT make it more verbose
- Preserve links and important context
- If it's already concise, return it as-is

Refined message:"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a message editor. Make messages clear and concise without adding verbosity."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=300
        )
        
        refined = response.choices[0].message.content.strip()
        print(f"Refined message (preview): {refined[:100]}...")
        return refined
    
    except Exception as e:
        print(f"Warning: Message refinement failed: {e}")
        return message_text  # Return original if refinement fails

# ---------------- SLACK INGESTION ----------------

def get_channels(limit: int = 50) -> List[Dict]:
    """Get list of Slack channels"""
    try:
        # First try public channels only
        data = slack_get("conversations.list", {
            "exclude_archived": True,
            "types": "public_channel",
            "limit": limit
        })
        return data.get("channels", [])
    except Exception as e:
        error_msg = str(e)
        if "missing_scope" in error_msg:
            print(f"\n❌ ERROR: Missing Slack API permissions!")
            print("\nYour Slack Bot Token needs these OAuth scopes:")
            print("  • channels:read - View basic channel info")
            print("  • channels:history - Read messages from public channels")
            print("  • users:read - View user information")
            print("\nOptional (for private channels):")
            print("  • groups:read - View private channel info")
            print("  • groups:history - Read private channel messages")
            print("\nTo add scopes:")
            print("1. Go to https://api.slack.com/apps")
            print("2. Select your app")
            print("3. Go to 'OAuth & Permissions'")
            print("4. Scroll to 'Scopes' → 'Bot Token Scopes'")
            print("5. Add the required scopes")
            print("6. Reinstall the app to your workspace")
            print("7. Copy the new 'Bot User OAuth Token' to your .env file\n")
        else:
            print(f"Error fetching channels: {e}")
        return []

def ingest_channel_messages(channel_id: str, channel_name: str, limit: int = 100, days_back: int = 365, max_messages: int = 200):
    """
    Ingest messages from a Slack channel within the time range.
    Filters for useful messages and includes thread replies.
    Uses pagination up to a maximum number of messages.
    
    Args:
        channel_id: Slack channel ID
        channel_name: Human-readable channel name
        limit: Number of messages to fetch per API request (max 1000)
        days_back: Only fetch messages from the last N days (default: 365 = 1 year)
        max_messages: Maximum total messages to fetch per channel (default: 1000)
    """
    print(f"\n=== Ingesting channel: #{channel_name} ===")
    print(f"Fetching up to {max_messages} messages from the last {days_back} days...")
    
    # Calculate oldest timestamp (1 year ago by default)
    oldest_timestamp = get_timestamp_for_days_ago(days_back)
    
    all_messages = []
    cursor = None
    page = 1
    
    try:
        # Paginate through messages up to max_messages limit
        while len(all_messages) < max_messages:
            print(f"  Fetching page {page}...")
            
            params = {
                "channel": channel_id,
                "limit": min(limit, 1000),  # Slack max is 1000 per request
                "oldest": oldest_timestamp
            }
            
            if cursor:
                params["cursor"] = cursor
            
            data = slack_get("conversations.history", params)
            messages = data.get("messages", [])
            all_messages.extend(messages)
            
            print(f"  → Got {len(messages)} messages (total so far: {len(all_messages)})")
            
            # Stop if we've hit the max_messages limit
            if len(all_messages) >= max_messages:
                print(f"  → Reached maximum of {max_messages} messages, stopping pagination")
                all_messages = all_messages[:max_messages]  # Trim to exact limit
                break
            
            # Check if there are more messages
            if not data.get("has_more", False):
                break
            
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            
            page += 1
        
        print(f"Fetched total of {len(all_messages)} messages from #{channel_name}")
        messages = all_messages
        
    except Exception as e:
        print(f"Error fetching messages from #{channel_name}: {e}")
        return
    
    user_cache = {}
    useful_count = 0
    
    for msg in messages:
        # Skip bot messages and system messages
        if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
            continue
        
        message_text = msg.get("text", "")
        if not message_text or len(message_text.strip()) < 10:
            continue
        
        user_id = msg.get("user", "unknown")
        user_name = get_user_name(user_id, user_cache)
        timestamp = msg.get("ts", "")
        
        # Check if this message was already processed
        doc_id = f"slack_msg_{channel_id}_{timestamp.replace('.', '_')}"
        # if document_exists(doc_id):
        #     print(f"⏭️  Skipping message from {user_name} (already processed)")
        #     continue
        
        # Check if message is useful
        if not is_useful_message(message_text):
            print(f"✗ Filtered out: {message_text[:60]}...")
            continue
        
        print(f"✓ Useful message from {user_name}: {message_text[:60]}...")
        
        # Fetch thread replies if this message has a thread
        thread_replies = []
        if msg.get("reply_count", 0) > 0:
            try:
                thread_data = slack_get("conversations.replies", {
                    "channel": channel_id,
                    "ts": timestamp
                })
                # Skip the first message (it's the parent)
                replies = thread_data.get("messages", [])[1:]
                
                for reply in replies:
                    reply_text = reply.get("text", "")
                    if reply_text and len(reply_text.strip()) >= 10:
                        reply_user = reply.get("user", "unknown")
                        reply_user_name = get_user_name(reply_user, user_cache)
                        
                        # Check if reply is useful
                        if is_useful_message(reply_text):
                            refined_reply = refine_message(reply_text, reply_user_name)
                            thread_replies.append({
                                "author": reply_user_name,
                                "text": refined_reply
                            })
                
                print(f"  → Included {len(thread_replies)} thread replies")
            except Exception as e:
                print(f"  → Error fetching thread: {e}")
        
        # Refine the main message
        refined_message = refine_message(message_text, user_name)
        
        # Build content with message and thread
        content = f"[{user_name}]: {refined_message}"
        
        if thread_replies:
            content += "\n\n--- Thread Replies ---\n"
            for reply in thread_replies:
                content += f"\n[{reply['author']}]: {reply['text']}\n"
        
        # Store in database
        upsert_doc(
            doc_id=doc_id,
            content=content,
            metadata={
                "tenant_id": TENANT_ID,
                "source": "slack",
                "channel": channel_name,
                "channel_id": channel_id,
                "author": user_name,
                "timestamp": timestamp,
                "has_thread": len(thread_replies) > 0,
                "thread_reply_count": len(thread_replies),
                "url": f"https://slack.com/archives/{channel_id}/p{timestamp.replace('.', '')}"
            }
        )
        
        useful_count += 1
    
    print(f"Ingested {useful_count} useful messages from #{channel_name}")

# ---------------- MAIN ----------------

def main(channel_names: Optional[List[str]] = None, message_limit: int = 200, days_back: int = 365, max_messages_per_channel: int = 1000):
    """
    Main function to ingest Slack messages.
    
    Args:
        channel_names: List of specific channel names to ingest (e.g., ['general', 'engineering'])
                      If None, will prompt or use all channels
        message_limit: Number of messages to fetch per API request (default 200, max 1000).
        days_back: Only ingest messages from the last N days (default: 365 = 1 year)
        max_messages_per_channel: Maximum total messages to fetch per channel (default: 1000)
    """
    print("Starting Slack ingestion...")
    print(f"Time range: Last {days_back} days ({days_back/365:.1f} years)")
    
    # Test connection first
    if not test_slack_connection():
        print("\nPlease fix the connection issues before continuing.")
        return
    
    # Get all channels
    # all_channels = get_channels()
    all_channels = [("C02H0BRTRLP","#settlements_developers"),("C0ZJSSQSV","#tech_devops"),("C0572CD6WQY","#platform_spine_edge_oncall"),("C012ZGQQFDJ","#tech_infra_edge"),("C0279AG4GUU","#dev-payments-banking")]
    print(f"Found {len(all_channels)} channels")
    
    # Filter channels if specific names provided
    if channel_names:
        channels_to_ingest = [
            ch for ch in all_channels 
            if ch["name"] in channel_names
        ]
        if not channels_to_ingest:
            print(f"Warning: None of the specified channels found: {channel_names}")
            return
    else:
        channels_to_ingest = all_channels
    
    print(f"Will ingest {len(channels_to_ingest)} channels")
    
    for id, channel in channels_to_ingest:
        try:
            ingest_channel_messages(
                channel_id=id,
                channel_name=channel,
                limit=message_limit,
                days_back=days_back,
                max_messages=max_messages_per_channel
            )
        except Exception as e:
            print(f"⚠️  WARNING: Failed to ingest channel {channel}: {e}")
            print(f"   Continuing with next channel...")
    
    print("\n=== Slack ingestion complete ===")

if __name__ == "__main__":
    ensure_collection()
    
    # Example: Ingest specific channels from the last year (max 1000 messages per channel)
    # main(channel_names=["general", "engineering", "product"], message_limit=200, days_back=365, max_messages_per_channel=1000)
    
    # Ingest all channels from the last year (max 200 messages per channel)
    main(message_limit=200, days_back=365, max_messages_per_channel=200)
    
    # For last 6 months only:
    # main(message_limit=200, days_back=180, max_messages_per_channel=1000)
    
    # For faster ingestion, increase message_limit to 1000 (Slack's max per request):
    # main(message_limit=1000, days_back=365, max_messages_per_channel=1000)
    
    # To fetch more messages per channel (e.g., 5000):
    # main(message_limit=1000, days_back=365, max_messages_per_channel=5000)

