import { useState, useEffect } from "react";
import { highlightUrls } from "../utils/urlHighlighter";
import "./SearchPage.css";

interface SearchResult {
  id: string;
  source: string;
  title: string;
  snippet: string;
  perma_link: string;
  metadata: {
    author?: string;
    date?: string;
    channel?: string;
    repo?: string;
    score?: number;
  };
}

interface SearchResponse {
  results: SearchResult[];
  total: number;
  enriched_query?: string;
  cache_hit?: boolean;
  memory?: {
    similar_queries?: Array<{ query: string; score: number }>;
    recent_history?: Array<{ query: string; timestamp: string }>;
    suggestions?: string[];
  };
}

const SearchPage = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [history, setHistory] = useState<Array<{ query: string; timestamp: string }>>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const userId = "user123"; // TODO: Get from auth context

  // Load history on mount
  useEffect(() => {
    fetch(`http://localhost:8000/api/v1/memory/history?user_id=${userId}&limit=10`)
      .then((res) => res.json())
      .then((data) => setHistory(data.history || []))
      .catch((err) => console.error("Failed to load history:", err));
  }, []);

  // Get suggestions as user types (debounced)
  useEffect(() => {
    if (query.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const timer = setTimeout(() => {
      fetch(`http://localhost:8000/api/v1/memory/suggestions?q=${encodeURIComponent(query)}&user_id=${userId}`)
        .then((res) => res.json())
        .then((data) => {
          setSuggestions(data.suggestions || []);
          setShowSuggestions(true);
        })
        .catch((err) => console.error("Failed to load suggestions:", err));
    }, 300); // Debounce 300ms

    return () => clearTimeout(timer);
  }, [query]);

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setHasSearched(true);
    setShowSuggestions(false);

    try {
      const response = await fetch("http://localhost:8000/api/v1/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: searchQuery, user_id: userId }),
      });

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data: SearchResponse = await response.json();
      setResults(data.results);
      
      // Update history from memory (but don't show suggestions after search)
      if (data.memory) {
        if (data.memory.recent_history) {
          setHistory(data.memory.recent_history);
        }
        // Don't update suggestions after search - they should only show while typing
      }
      
      // Clear suggestions after search
      setSuggestions([]);
      setShowSuggestions(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred while searching"
      );
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResultClick = async (resultId: string) => {
    // Track click
    try {
      await fetch("http://localhost:8000/api/v1/memory/click", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query,
          result_id: resultId,
          user_id: userId,
        }),
      });
    } catch (err) {
      console.error("Failed to track click:", err);
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
              onFocus={() => {
                if (query.length >= 2 && !hasSearched) {
                  setShowSuggestions(true);
                }
              }}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              onKeyDown={(e) => {
                // Hide suggestions when Enter is pressed
                if (e.key === 'Enter') {
                  setShowSuggestions(false);
                }
              }}
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
          
          {/* Suggestions Dropdown - only show when typing, not after search */}
          {showSuggestions && suggestions.length > 0 && !hasSearched && (
            <div className="suggestions-dropdown">
              {suggestions.map((suggestion, idx) => (
                <div
                  key={idx}
                  className="suggestion-item"
                  onClick={() => {
                    setQuery(suggestion);
                    setShowSuggestions(false);
                    handleSearch(suggestion);
                  }}
                >
                  {suggestion}
                </div>
              ))}
            </div>
          )}
        </form>

        {/* Recent History */}
        {history.length > 0 && !hasSearched && (
          <div className="history-section">
            <h3 className="history-title">Recent Searches</h3>
            <div className="history-items">
              {history.slice(0, 5).map((item, idx) => (
                <button
                  key={idx}
                  className="history-item"
                  onClick={() => {
                    setQuery(item.query);
                    handleSearch(item.query);
                  }}
                >
                  {item.query}
                </button>
              ))}
            </div>
          </div>
        )}

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
                    <div key={result.id} onClick={() => handleResultClick(result.id)}>
                      <SearchResultCard result={result} />
                    </div>
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
  return (
    <div className="result-card" style={{ cursor: "pointer" }}>
      <div className="result-header">
        <h3 className="result-title">{result.title}</h3>
        <span className="result-source">
          Source: {result.source === "slack" ? "Slack" : "GitHub"}
        </span>
      </div>
      <div className="result-body">
        <div className="result-snippet">{highlightUrls(result.snippet)}</div>
        <div className="result-link-section">
          <strong>Link:</strong> {highlightUrls(result.perma_link, true)}
        </div>
        {result.metadata.author && (
          <div className="result-metadata">
            {result.source === "slack" ? "Channel" : "Repo"}:{" "}
            {result.metadata.channel || result.metadata.repo} • Author:{" "}
            {result.metadata.author} • {result.metadata.date}
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchPage;
