import { useState } from "react";
import { highlightUrls } from "../utils/urlHighlighter";
import "./SearchPage.css";

interface SearchResult {
  id: string;
  source: string;
  title: string;
  snippet: string;
  content: string;
  summary?: string;  // LLM-generated summary
  perma_link: string;
  metadata: {
    // Common fields
    tenant_id?: string;
    score?: number;
    
    // GitHub fields
    repo?: string;
    type?: string;  // 'readme', 'pr', 'commit'
    author?: string;
    merged_at?: string;
    base_branch?: string;
    branch?: string;
    commit_count?: number;
    
    // Slack fields
    channel?: string;
    channel_id?: string;
    timestamp?: string;
    has_thread?: boolean;
    thread_reply_count?: number;
    
    // Common
    url?: string;
  };
}

interface SearchResponse {
  results: SearchResult[];
  total: number;
  enriched_query?: string;
  cache_hit?: boolean;
}

const SearchPage = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await fetch("http://localhost:8000/api/v1/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: searchQuery }),
      });

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data: SearchResponse = await response.json();
      setResults(data.results);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred while searching"
      );
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (query.trim()) {
      handleSearch(query);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  };

  return (
    <div className="search-page">
      <div className="search-container">
        {/* Header */}
        <div className="search-header">
          <h1 className="search-title">RazorSearch</h1>
          <p className="search-subtitle">Search across Slack and GitHub</p>
        </div>

        {/* Search Input */}
        <form onSubmit={handleSubmit} className="search-form">
          <div className="search-input-wrapper">
            <input
              type="text"
              className="search-input"
              placeholder="Enter your search query..."
              value={query}
              onChange={handleChange}
              disabled={isLoading}
            />
            <button
              type="submit"
              className="search-button"
              disabled={isLoading || !query.trim()}
            >
              {isLoading ? "..." : "🔍"}
            </button>
          </div>
        </form>

        {/* Loading State */}
        {isLoading && (
          <div className="loading-container">
            <div className="spinner"></div>
            <p>Loading search results...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="error-message">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Results */}
        {!isLoading && hasSearched && (
          <div className="results-container">
            {results.length === 0 ? (
              <div className="no-results">
                <p className="no-results-text">
                  No results found for "{query}"
                </p>
                <p className="no-results-hint">Try a different search query</p>
              </div>
            ) : (
              <>
                <p className="results-count">
                  Found {results.length} result{results.length !== 1 ? "s" : ""}
                </p>
                <div className="results-list">
                  {results.map((result) => (
                    <SearchResultCard key={result.id} result={result} />
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

interface SearchResultCardProps {
  result: SearchResult;
}

const SearchResultCard = ({ result }: SearchResultCardProps) => {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return null;
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      });
    } catch {
      return dateStr;
    }
  };

  const formatSlackUserId = (userId: string) => {
    // Format Slack user ID to be more readable
    if (userId && userId.startsWith('U') && userId.length > 5) {
      return `User ${userId.substring(0, 8)}...`;
    }
    return userId;
  };

  const renderMetadata = () => {
    const parts: string[] = [];
    
    if (result.source === "github") {
      if (result.metadata.repo) {
        parts.push(`Repo: ${result.metadata.repo}`);
      }
      if (result.metadata.type) {
        const typeLabel = result.metadata.type === "pr" ? "Pull Request" 
                        : result.metadata.type === "readme" ? "README"
                        : result.metadata.type === "commit" ? "Commits"
                        : result.metadata.type;
        parts.push(`Type: ${typeLabel}`);
      }
      if (result.metadata.author) {
        parts.push(`Author: ${result.metadata.author}`);
      }
      if (result.metadata.merged_at) {
        const formattedDate = formatDate(result.metadata.merged_at);
        if (formattedDate) parts.push(`Merged: ${formattedDate}`);
      }
      if (result.metadata.base_branch) {
        parts.push(`Branch: ${result.metadata.base_branch}`);
      }
      if (result.metadata.commit_count) {
        parts.push(`${result.metadata.commit_count} commits`);
      }
    } else if (result.source === "slack") {
      if (result.metadata.channel) {
        parts.push(`${result.metadata.channel}`);
      }
      if (result.metadata.timestamp) {
        const date = new Date(parseFloat(result.metadata.timestamp) * 1000);
        const formattedDate = date.toLocaleDateString('en-US', { 
          year: 'numeric', 
          month: 'short', 
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        });
        parts.push(formattedDate);
      }
      if (result.metadata.has_thread && result.metadata.thread_reply_count) {
        parts.push(`💬 ${result.metadata.thread_reply_count} ${result.metadata.thread_reply_count === 1 ? 'reply' : 'replies'}`);
      }
    }
    
    if (result.metadata.score !== undefined) {
      parts.push(`Relevance: ${(result.metadata.score * 100).toFixed(0)}%`);
    }
    
    return parts.join(" • ");
  };

  return (
    <div className="result-card">
      <div className="result-header">
        <h3 className="result-title">{result.title}</h3>
        <span className="result-source">
          Source: {result.source === "slack" ? "Slack" : "GitHub"}
        </span>
      </div>
      <div className="result-body">
        {result.summary && (
          <div className="result-summary">
            <div className="summary-icon">💡</div>
            <div className="summary-text">{result.summary}</div>
          </div>
        )}
        <div className="result-snippet">{highlightUrls(result.snippet)}</div>
        <div className="result-footer">
          {renderMetadata() && (
            <div className="result-metadata">{renderMetadata()}</div>
          )}
          {result.perma_link && (
            <a 
              href={result.perma_link} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="result-link"
            >
              View {result.source === "slack" ? "in Slack" : "on GitHub"} →
            </a>
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchPage;
