import React from 'react'

// URL regex pattern - matches http, https, and common URL patterns
const URL_REGEX = /(https?:\/\/[^\s]+)/gi

/**
 * Highlights URLs in text and makes them clickable
 * @param text - The text that may contain URLs
 * @param isUrlOnly - If true, the entire text is treated as a URL
 * @returns React elements with highlighted and clickable URLs
 */
export const highlightUrls = (
  text: string,
  isUrlOnly: boolean = false
): React.ReactNode => {
  if (isUrlOnly) {
    // If the entire text is a URL, render it as a single link
    return (
      <a
        href={text}
        target="_blank"
        rel="noopener noreferrer"
      >
        {text}
      </a>
    )
  }

  // Split text by URLs and create React elements
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  // Reset regex lastIndex
  URL_REGEX.lastIndex = 0

  while ((match = URL_REGEX.exec(text)) !== null) {
    // Add text before the URL
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index))
    }

    // Add the URL as a clickable link
    const url = match[0]
    parts.push(
      <a
        key={`url-${match.index}`}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {url}
      </a>
    )

    lastIndex = URL_REGEX.lastIndex
  }

  // Add remaining text after the last URL
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex))
  }

  // If no URLs were found, return the original text
  if (parts.length === 0) {
    return text
  }

  return <>{parts}</>
}

