# RazorSearch Frontend

Frontend application for RazorSearch built with React, TypeScript, Vite, and Blade Design System.

## Features

- 🔍 **Search Interface**: Clean search input with loading states
- 📊 **Results Display**: Beautiful card-based results layout
- 🔗 **URL Highlighting**: Automatically detects and highlights URLs in results
- 🖱️ **Clickable Links**: URLs open in new tabs when clicked
- ⚡ **Fast**: Built with Vite for lightning-fast development
- 🎨 **Blade Design System**: Consistent UI using Razorpay's Blade components

## Setup

1. Install dependencies:
```bash
npm install --legacy-peer-deps
```

2. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Backend Integration

Make sure the backend API is running on `http://localhost:8000` before using the search functionality.

The frontend is configured to proxy API requests to the backend through Vite's proxy configuration.

