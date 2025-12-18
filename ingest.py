import os
import base64
import time
import requests
from typing import List, Dict
from dotenv import load_dotenv
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct,VectorParams, Distance
from openai import OpenAI
from openai import AzureOpenAI

# ---------------- CONFIG ----------------
load_dotenv()
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ORG = os.environ["ORG_NAME"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

COLLECTION_NAME = "documents"
TENANT_ID = ORG  # tenant == org

VECTOR_SIZE = os.environ["VECTOR_SIZE"] # text-embedding-3-small
MODEL_ENDPOINT = os.environ["MODEL_ENDPOINT"]
MODEL_KEY = os.environ["MODEL_KEY"]
MODEL_VERSION = os.environ["MODEL_VERSION"]
MODEL_DEPLOYMENT = os.environ["MODEL_DEPLOYMENT"]
print(MODEL_DEPLOYMENT)
print(MODEL_KEY)
print(MODEL_VERSION)
print(MODEL_ENDPOINT)

client = AzureOpenAI(
    api_key=OPENAI_API_KEY,
    azure_endpoint="https://fy26-hackon-q3.openai.azure.com/",
    api_version="2024-02-01"  
)

model_client= AzureOpenAI(
    api_key=MODEL_KEY,
    azure_endpoint=MODEL_ENDPOINT,
    api_version=MODEL_VERSION
)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

qdrant = QdrantClient(url="http://localhost:6333")

# ---------------- HELPERS ----------------

def github_get(url: str):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    time.sleep(0.2)  # rate-limit safety
    return resp.json()

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
        
        prompt = f"""This content is too long for embedding. Create a comprehensive but concise summary that preserves:
- Key technical details
- Important decisions and changes
- Action items and outcomes
- Critical context

Keep it under 1500 words maximum.

Content to summarize:
{text_to_summarize}

Concise summary:"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a technical summarizer. Create comprehensive but concise summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Add note about summarization
        result = f"{summary}\n\n[Note: This content was summarized due to length constraints]"
        
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
    # Ensure text fits within token limit
    chunked_text = chunk_text(text)
    
    res = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunked_text
    )
    return res.data[0].embedding

def enrich_with_llm(content: str, content_type: str = "PR") -> str:
    """
    Use LLM to add context and analysis to the content before storing.
    
    Args:
        content: The original content to enrich
        content_type: Type of content (PR, commit, readme, etc.)
    
    Returns:
        Enriched content with additional context
    """
    try:
        prompt = f"""Analyze the following {content_type} and provide:
1. A concise summary (2-3 sentences)
2. Key technical changes or features mentioned
3. Relevant keywords and technologies
4. Potential impact or importance

Keep the enrichment concise and focused on information retrieval.

Original Content:
{content}

Provide the enriched analysis:"""

        response = model_client.chat.completions.create(
            model=MODEL_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes code changes and documentation to extract key information for search and retrieval."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        enrichment = response.choices[0].message.content
        print(enrichment)
        
        # Combine original content with LLM enrichment
        enriched_content = f"""{content}

--- AI-Generated Context ---
{enrichment}"""
        
        return enriched_content
    
    except Exception as e:
        print(f"Warning: LLM enrichment failed: {e}")
        return content  # Return original content if enrichment fails

def is_useful_commit(commit_message: str) -> bool:
    """
    Use LLM to determine if a commit message is useful for documentation.
    
    Filters out:
    - Version bumps
    - Merge commits without context
    - Trivial formatting changes
    - Auto-generated commits
    
    Args:
        commit_message: The commit message to evaluate
    
    Returns:
        True if the commit is useful, False otherwise
    """
    try:
        prompt = f"""Evaluate if this commit message is useful for code documentation and search.

Commit Message:
{commit_message}

Consider it USEFUL if it contains:
- Feature implementations or enhancements
- Bug fixes with context
- Architecture or design changes
- Important refactoring
- Security or performance improvements

Consider it NOT USEFUL if it's:
- Version bumps (e.g., "Bump version to X.Y.Z")
- Simple merge commits without context
- Trivial formatting/whitespace changes
- Auto-generated messages
- Minor typo fixes

Respond with ONLY "USEFUL" or "NOT_USEFUL":"""

        response = model_client.chat.completions.create(
            model=MODEL_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a commit message evaluator. Respond with only 'USEFUL' or 'NOT_USEFUL'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip().upper()
        print(result)
        
        # Check for NOT_USEFUL first (takes precedence)
        if "NOT_USEFUL" in result or "NOT USEFUL" in result:
            return False
        # Then check for USEFUL
        elif "USEFUL" in result:
            return True
        else:
            # If response is unclear, default to including the commit
            print(f"Warning: Unclear response from LLM: {result}")
            return True
    
    except Exception as e:
        print(f"Warning: Commit usefulness check failed: {e}")
        return True  # Default to including if check fails

def ensure_collection():
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
    try:
        vector = embed(content)
        new = str_to_uuid(doc_id)
        print(new)
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=new,
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

# ---------------- INGESTION ----------------

def ingest_repos(limit=5):
    repos = github_get(f"https://api.github.com/orgs/{ORG}/repos")
    return repos[:limit]

def ingest_readme(repo_name: str):
    doc_id = f"gh_readme_{repo_name}"
    
    # Check if README was already processed
    if document_exists(doc_id):
        print(f"⏭️  Skipping README for {repo_name} (already processed)")
        return
    
    try:
        data = github_get(
            f"https://api.github.com/repos/{ORG}/{repo_name}/readme"
        )
    except Exception as e:
        print(f"⚠️  Could not fetch README for {repo_name}: {e}")
        return

    try:
        content = base64.b64decode(data["content"]).decode("utf-8")

        upsert_doc(
            doc_id=doc_id,
            content=content,
            metadata={
                "tenant_id": TENANT_ID,
                "source": "github",
                "repo": repo_name,
                "type": "readme",
                "url": f"https://github.com/{ORG}/{repo_name}"
            }
        )
    except Exception as e:
        print(f"⚠️  WARNING: Failed to ingest README for {repo_name}: {e}")

def ingest_prs(repo_name: str, limit=30):
    # Fetch closed PRs (merged PRs are a subset of closed PRs)
    prs = github_get(
        f"https://api.github.com/repos/{ORG}/{repo_name}/pulls?state=closed&per_page={limit}"
    )

    for pr in prs:
        # Only process PRs that are merged into master/main branch
        if not pr.get('merged_at'):
            continue
        
        base_branch = pr.get('base', {}).get('ref', '')
        if base_branch not in ['master', 'main']:
            continue
        
        # Check if this PR was already processed
        doc_id = f"gh_pr_{repo_name}_{pr['number']}"
        if document_exists(doc_id):
            print(f"⏭️  Skipping PR #{pr['number']} (already processed)")
            continue
        
        # Fetch comments for the PR to include bot descriptions
        bot_comments = []
        try:
            comments = github_get(pr['comments_url'])
            for comment in comments:
                # Check if comment is from a bot (github-actions[bot], etc.)
                user_login = comment.get('user', {}).get('login', '')
                if '[bot]' in user_login or comment.get('user', {}).get('type') == 'Bot':
                    bot_comments.append({
                        'author': user_login,
                        'body': comment.get('body', '')
                    })
        except Exception as e:
            print(f"Warning: Could not fetch comments for PR #{pr['number']}: {e}")
        
        # Build the content with PR details and bot comments
        text = f"""
        PR #{pr['number']} – {pr['title']}

        {pr['body'] or ''}
        """.strip()
        
        # Append bot comments if any
        if bot_comments:
            text += "\n\n--- Bot Comments ---\n"
            for bot_comment in bot_comments:
                text += f"\n[{bot_comment['author']}]:\n{bot_comment['body']}\n"

        # Enrich content with LLM analysis before storing
        enriched_text = enrich_with_llm(text, content_type="PR")

        upsert_doc(
            doc_id=doc_id,
            content=enriched_text,
            metadata={
                "tenant_id": TENANT_ID,
                "source": "github",
                "repo": repo_name,
                "type": "pr",
                "author": pr["user"]["login"],
                "merged_at": pr['merged_at'],
                "base_branch": base_branch,
                "url": pr["html_url"]
            }
        )

def ingest_commits(repo_name: str, batch_size=5):
    # Fetch commits from master branch only
    # Try 'master' first, fallback to 'main' if it doesn't exist
    commits = None
    for branch in ['master', 'main']:
        try:
            commits = github_get(
                f"https://api.github.com/repos/{ORG}/{repo_name}/commits?sha={branch}&per_page=50"
            )
            print(f"Fetching commits from '{branch}' branch for {repo_name}")
            break
        except Exception as e:
            print(f"Branch '{branch}' not found, trying next: {e}")
            continue
    
    if not commits:
        print(f"Warning: Could not fetch commits from master/main for {repo_name}")
        return

    # Filter commits using LLM to only include useful ones
    useful_commits = []
    for commit in commits:
        message = commit["commit"]["message"]
        
        # Use LLM to determine if commit is useful
        if is_useful_commit(message):
            useful_commits.append({
                "message": message,
                "sha": commit["sha"],
                "author": commit["commit"]["author"]["name"],
                "date": commit["commit"]["author"]["date"]
            })
            print(f"✓ Useful commit: {message[:60]}...")
        else:
            print(f"✗ Filtered out: {message[:60]}...")
    
    print(f"Filtered {len(useful_commits)} useful commits out of {len(commits)} total")

    # Batch useful commits and enrich with LLM
    for i in range(0, len(useful_commits), batch_size):
        doc_id = f"gh_commit_{repo_name}_{i//batch_size}"
        
        # Check if this commit batch was already processed
        if document_exists(doc_id):
            print(f"⏭️  Skipping commit batch {i//batch_size} (already processed)")
            continue
        
        chunk = useful_commits[i:i+batch_size]
        content = "Recent commits from master:\n" + "\n".join(
            f"- [{c['sha'][:7]}] {c['message']} (by {c['author']})" 
            for c in chunk
        )

        # Enrich commit batch with LLM analysis
        enriched_content = enrich_with_llm(content, content_type="commit batch")

        upsert_doc(
            doc_id=doc_id,
            content=enriched_content,
            metadata={
                "tenant_id": TENANT_ID,
                "source": "github",
                "repo": repo_name,
                "type": "commit",
                "branch": "master/main",
                "commit_count": len(chunk),
                "url": f"https://github.com/{ORG}/{repo_name}/commits"
            }
        )

# ---------------- MAIN ----------------

def main():
    print("Starting GitHub ingestion...")
    # repos = ingest_repos()
    repos = ["settlements","payouts","ledger","spinacode","edge","kube-manifests","vishnu","terraform-kong","authz"]
    print(repos)

    for repo in repos:
        # name = repo["name"]
        name= repo
        print(f"\n=== Ingesting repo: {name} ===")

        try:
            ingest_readme(name)
        except Exception as e:
            print(f"⚠️  WARNING: Failed to ingest README for {name}: {e}")
        
        try:
            ingest_prs(name)
        except Exception as e:
            print(f"⚠️  WARNING: Failed to ingest PRs for {name}: {e}")
        
        try:
            ingest_commits(name)
        except Exception as e:
            print(f"⚠️  WARNING: Failed to ingest commits for {name}: {e}")

    print("\n=== Ingestion complete ===")

if __name__ == "__main__":
    ensure_collection()
    main()
