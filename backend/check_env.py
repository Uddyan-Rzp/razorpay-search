#!/usr/bin/env python3
"""
Quick script to check environment variables
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 50)
print("Environment Variables Check")
print("=" * 50)

# Check LLM Azure OpenAI Configuration
llm_endpoint = os.getenv("LLM_AZURE_ENDPOINT")
llm_key = os.getenv("LLM_AZURE_API_KEY")
llm_version = os.getenv("LLM_AZURE_API_VERSION")

if llm_endpoint:
    print(f"✓ LLM_AZURE_ENDPOINT: {llm_endpoint}")
else:
    print("✗ LLM_AZURE_ENDPOINT: NOT SET")

if llm_key:
    print(f"✓ LLM_AZURE_API_KEY: Set")
    print(f"  Length: {len(llm_key)} characters")
    print(f"  Starts with: {llm_key[:7]}...")
    print(f"  Ends with: ...{llm_key[-4:]}")
else:
    print("✗ LLM_AZURE_API_KEY: NOT SET")
    print("  Please set it in .env file")

if llm_version:
    print(f"✓ LLM_AZURE_API_VERSION: {llm_version}")
else:
    print("✗ LLM_AZURE_API_VERSION: NOT SET")

print()

# Check Embedding Azure OpenAI Configuration
embedding_endpoint = os.getenv("EMBEDDING_AZURE_ENDPOINT")
embedding_key = os.getenv("EMBEDDING_AZURE_API_KEY")
embedding_version = os.getenv("EMBEDDING_AZURE_API_VERSION")

if embedding_endpoint:
    print(f"✓ EMBEDDING_AZURE_ENDPOINT: {embedding_endpoint}")
else:
    print("✗ EMBEDDING_AZURE_ENDPOINT: NOT SET")

if embedding_key:
    print(f"✓ EMBEDDING_AZURE_API_KEY: Set")
    print(f"  Length: {len(embedding_key)} characters")
    print(f"  Starts with: {embedding_key[:7]}...")
    print(f"  Ends with: ...{embedding_key[-4:]}")
else:
    print("✗ EMBEDDING_AZURE_API_KEY: NOT SET")
    print("  Please set it in .env file")

if embedding_version:
    print(f"✓ EMBEDDING_AZURE_API_VERSION: {embedding_version}")
else:
    print("✗ EMBEDDING_AZURE_API_VERSION: NOT SET")

print()

# Check Qdrant URL
qdrant_url = os.getenv("QDRANT_URL")
if qdrant_url:
    print(f"✓ QDRANT_URL: {qdrant_url}")
else:
    print("✗ QDRANT_URL: NOT SET")

print()

# Check other important vars
print()
print("Deployment Configuration:")
print(f"  LLM_DEPLOYMENT: {os.getenv('LLM_DEPLOYMENT', 'not set')}")
print(f"  LLM_MODEL: {os.getenv('LLM_MODEL', 'not set')}")
print(f"  EMBEDDING_DEPLOYMENT: {os.getenv('EMBEDDING_DEPLOYMENT', 'not set')}")
print(f"  EMBEDDING_MODEL: {os.getenv('EMBEDDING_MODEL', 'not set')}")

print()
print("Other Configuration:")
print(f"  VECTOR_DB_PROVIDER: {os.getenv('VECTOR_DB_PROVIDER', 'not set')}")
print(f"  QDRANT_COLLECTION_NAME: {os.getenv('QDRANT_COLLECTION_NAME', 'not set')}")

print("=" * 50)

