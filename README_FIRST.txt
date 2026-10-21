AURAVIS FINAL — OLD FEATURES PRESERVED + SEARCH/PERSONALIZATION FIXED

IMPORTANT: Use this folder as a clean installation. Do not copy app.py or data files from an older AURAVIS folder over this version.

1) Open CMD in the folder that contains app.py.
2) Run:
   python -m venv venv
3) Run:
   venv\Scripts\activate.bat
4) Run:
   python -m pip install -r requirements.txt
5) Run:
   python app.py
6) Open:
   http://127.0.0.1:5000

This version keeps the V5-style search page and restores/keeps:
- Education / Movies selection
- Search box and working POST search (no API key required)
- Old search history
- AI Profile
- Learned preferences from searches, clicks, views and likes
- Personalized ranking / preference boost
- Made-for-you recommendations
- Like / Not Interested mutual exclusivity
- Clicking the active Like removes it
- Clicking the active Not Interested removes it
- Clicking the opposite preference switches to it
- Per-user SQLite history and preferences
- Profile picture and username
- Light/dark mode
- Voice search
- Multilingual query aliases (English/Tamil/Hindi/Spanish)
- Image Search upload control
- Details/resource page
- Real source URL buttons from the CSV data

Preference rule:
A result can have exactly one of: no preference, Like, Not Interested.
The database enforces this with UNIQUE(user_id, category, content_id).

The core search uses the local CSV data, so TMDB/OpenAI/YouTube keys are NOT required to search.


VISION AI SETUP
----------------
AURAVIS now uses the OpenAI Responses API for real image understanding.
1. Copy .env.example to .env
2. Put your own OpenAI API key after OPENAI_API_KEY=
3. Never share or commit your .env file.
4. Install requirements and restart AURAVIS.

CMD:
copy .env.example .env
notepad .env
python -m pip install -r requirements.txt
python app.py

Image Search flow: choose image -> Vision AI creates a concise query -> query appears in the normal AURAVIS search box -> click Search with AI.
All existing local Education/Movies search, history, personalization, Like/Not Interested, profile, theme and voice features are preserved.

MOVIES 1000 (V13.5)
-------------------
Education already contains 1000 local records.
To expand Movies from the bundled fallback set to 1000 real movie records, run once while online:
    python prepare_movies_1000.py
After it says READY, data\movies.csv is stored locally and works offline.
