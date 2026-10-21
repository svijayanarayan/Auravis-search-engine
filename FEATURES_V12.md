# AURAVIS V12 — Goal-Aware Offline Adaptive Search

New differentiation layer added without removing the existing V8/V9/V11 features:

- Goal modes: Learn, Exam, Build, Research, Explore
- User knowledge level: Beginner, Intermediate, Advanced
- Goal-aware re-ranking on top of query relevance + learned preferences
- Explainable “Why this result?” reason on every result
- Search Journey connecting recent searches
- Adaptive Knowledge Map built from education activity
- Offline-first core: local CSV search, SQLite history/preferences/profile and ranking do not require internet
- PWA-style service worker caches the interface/offline page
- Network indicator explains which features remain available offline
- Vision AI remains available when an OpenAI API key + internet are available
- Existing logo glow → spoken greeting → voice search, image search, theme, history, profile, likes/not-interested and recommendations preserved

Important: offline means the local Flask app can run without an internet connection. External websites/APIs and cloud Vision AI naturally require internet.

## V12.1 — In-page learning
- Education detail pages always show an AURAVIS learning document generated from the local dataset; no click-away is required and the text remains available offline.
- When `YOUTUBE_API_KEY` is configured, AURAVIS uses the official YouTube Data API to find one embeddable, syndicated, strict-safe-search educational video and displays it directly in the detail page.
- If the network/API is unavailable, the local learning document still works and the page degrades gracefully.
