import os
import base64
import time
import requests
from typing import List, Dict
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from openai import OpenAI
from openai import AzureOpenAI

# ---------------- CONFIG ----------------
load_dotenv()
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ORG = os.environ["ORG_NAME"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

COLLECTION_NAME = "documents"
TENANT_ID = ORG  # tenant == org



client = AzureOpenAI(
    api_key=OPENAI_API_KEY,
    azure_endpoint="https://fy26-hackon-q3.openai.azure.com/",
    api_version="2023-05-15"
    
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

def embed(text: str) -> List[float]:
    res = client.embeddings.create(
        model="fy26-hackon-q3-emb",
        input=text
    )
    return res.data[0].embedding

def upsert_doc(doc_id: str, content: str, metadata: Dict):
    vector = embed(content)

    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=doc_id,
                vector=vector,
                payload={
                    "content": content,
                    **metadata
                }
            )
        ]
    )

# ---------------- INGESTION ----------------

def ingest_repos(limit=5):
    repos = github_get(f"https://api.github.com/orgs/{ORG}/repos")
    return repos[:limit]

def ingest_readme(repo_name: str):
    try:
        data = github_get(
            f"https://api.github.com/repos/{ORG}/{repo_name}/readme"
        )
    except Exception:
        return

    content = base64.b64decode(data["content"]).decode("utf-8")

    doc_id = f"gh_readme_{repo_name}"
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

def ingest_prs(repo_name: str, limit=30):
    prs = github_get(
        f"https://api.github.com/repos/{ORG}/{repo_name}/pulls?state=all&per_page={limit}"
    )

    for pr in prs:
        text = f"""
        PR #{pr['number']} – {pr['title']}

        {pr['body'] or ''}
        """.strip()

        doc_id = f"gh_pr_{repo_name}_{pr['number']}"
        upsert_doc(
            doc_id=doc_id,
            content=text,
            metadata={
                "tenant_id": TENANT_ID,
                "source": "github",
                "repo": repo_name,
                "type": "pr",
                "author": pr["user"]["login"],
                "url": pr["html_url"]
            }
        )

def ingest_commits(repo_name: str, batch_size=5):
    commits = github_get(
        f"https://api.github.com/repos/{ORG}/{repo_name}/commits?per_page=50"
    )

    messages = [c["commit"]["message"] for c in commits]

    for i in range(0, len(messages), batch_size):
        chunk = messages[i:i+batch_size]
        content = "Recent commits:\n" + "\n".join(f"- {m}" for m in chunk)

        doc_id = f"gh_commit_{repo_name}_{i//batch_size}"
        upsert_doc(
            doc_id=doc_id,
            content=content,
            metadata={
                "tenant_id": TENANT_ID,
                "source": "github",
                "repo": repo_name,
                "type": "commit",
                "url": f"https://github.com/{ORG}/{repo_name}/commits"
            }
        )

# ---------------- MAIN ----------------

def main():
    print("Starting GitHub ingestion...")
    repos = ingest_repos()
    print(repos)

    for repo in repos:
        name = repo["name"]
        print(f"Ingesting repo: {name}")

        ingest_readme(name)
        ingest_prs(name)
        ingest_commits(name)

    print("Ingestion complete.")

if __name__ == "__main__":
    
    main()
