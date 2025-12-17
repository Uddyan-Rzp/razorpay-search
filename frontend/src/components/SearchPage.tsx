import { useState } from "react";
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
  return (
    <div className="result-card">
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
