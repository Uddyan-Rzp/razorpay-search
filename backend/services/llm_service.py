"""
LLM Service for query enrichment and processing
"""
import os
from typing import Optional
from config import Config


class LLMService:
    """Service for interacting with LLM providers"""
    
    def __init__(self):
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the LLM client using Azure OpenAI"""
        try:
            from openai import AzureOpenAI
            if not Config.LLM_AZURE_API_KEY:
                raise ValueError("LLM_AZURE_API_KEY not set in environment variables")
            import httpx
            http_client = httpx.Client(
                timeout=30.0,
                verify=Config.VERIFY_SSL
            )
            self.client = AzureOpenAI(
                api_version=Config.LLM_AZURE_API_VERSION,
                azure_endpoint=Config.LLM_AZURE_ENDPOINT,
                api_key=Config.LLM_AZURE_API_KEY,
                http_client=http_client,
                max_retries=2
            )
            self.deployment = Config.LLM_DEPLOYMENT
            self.model = Config.LLM_MODEL
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
    
    async def enrich_query(self, query: str) -> str:
        """
        Enrich the user query using LLM to improve search results.
        This can expand the query, add synonyms, or reformulate it.
        """
        if not Config.ENABLE_QUERY_ENRICHMENT:
            return query
        
        prompt = f"""You are a search query enhancement assistant. Your task is to improve the following search query to make it more effective for semantic search across technical documentation, Slack messages, and GitHub issues.

Original query: {query}

Please provide an enhanced version of this query that:
1. Preserves the original intent
2. Adds relevant technical terms and synonyms
3. Expands acronyms if appropriate
4. Makes it more suitable for semantic search

Return only the enhanced query, nothing else."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,  # Azure OpenAI uses deployment name
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that enhances search queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            enriched_query = response.choices[0].message.content.strip()
            return enriched_query if enriched_query else query
            
        except Exception as e:
            # If LLM fails, raise exception so caller can handle it
            error_type = type(e).__name__
            error_msg = str(e)
            if "API key" in error_msg or "authentication" in error_msg.lower():
                raise ValueError(f"LLM authentication failed. Please check your API key in .env file. Error: {error_msg}")
            elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                raise ConnectionError(f"LLM connection failed. Please check your internet connection and API key. Error: {error_msg}")
            else:
                raise Exception(f"LLM query enrichment failed: {error_type}: {error_msg}")
    
    async def generate_context(self, query: str, results: list) -> Optional[str]:
        """
        Generate contextual summary or answer based on search results.
        This can be used to provide AI-generated summaries of the results.
        """
        if not results:
            return None
        
        # Format results for context
        results_text = "\n\n".join([
            f"Title: {r.get('title', 'N/A')}\nSnippet: {r.get('snippet', 'N/A')}"
            for r in results[:5]  # Use top 5 results
        ])
        
        prompt = f"""Based on the following search results for the query "{query}", provide a concise summary or answer.

Search Results:
{results_text}

Provide a brief summary that answers the query based on these results."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,  # Azure OpenAI uses deployment name
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes search results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"LLM context generation failed: {e}")
            return None

