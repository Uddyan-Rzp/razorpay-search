"""
Embedding Service for converting text to vectors
"""
import os
from typing import List
from config import Config


class EmbeddingService:
    """Service for generating embeddings from text"""
    
    def __init__(self):
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the embedding client using Azure OpenAI"""
        try:
            from openai import AzureOpenAI
            if not Config.EMBEDDING_AZURE_API_KEY:
                raise ValueError("EMBEDDING_AZURE_API_KEY not set in environment variables")
            import httpx
            http_client = httpx.Client(
                timeout=30.0,
                verify=Config.VERIFY_SSL
            )
            self.client = AzureOpenAI(
                api_version=Config.EMBEDDING_AZURE_API_VERSION,
                azure_endpoint=Config.EMBEDDING_AZURE_ENDPOINT,
                api_key=Config.EMBEDDING_AZURE_API_KEY,
                http_client=http_client,
                max_retries=2
            )
            self.deployment = Config.EMBEDDING_DEPLOYMENT
            self.model = Config.EMBEDDING_MODEL
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for a given text
        """
        try:
            response = self.client.embeddings.create(
                model=self.deployment,  # Azure OpenAI uses deployment name
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            if "certificate" in error_msg.lower() or "SSL" in error_msg or "CERTIFICATE_VERIFY_FAILED" in error_msg:
                raise ConnectionError(
                    f"SSL certificate verification failed. "
                    f"This is often a macOS certificate issue. "
                    f"Try: Install Certificates.command from Python folder, or set VERIFY_SSL=false in .env (not recommended). "
                    f"Error: {error_msg}"
                )
            elif "Connection" in error_type or "connection" in error_msg.lower():
                raise ConnectionError(
                    f"Failed to connect to Azure OpenAI API. "
                    f"Please check your internet connection and firewall settings. "
                    f"Error: {error_msg}"
                )
            elif "API key" in error_msg or "authentication" in error_msg.lower():
                raise ValueError(
                    f"Azure OpenAI API authentication failed. Please check your API key. "
                    f"Error: {error_msg}"
                )
            else:
                raise Exception(f"Azure OpenAI embedding generation failed: {error_type}: {error_msg}")

