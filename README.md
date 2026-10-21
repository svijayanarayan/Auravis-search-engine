# AURAVIS V5 — AI Personalized Search & Recommendation Engine

AURAVIS is a second-year CSE project that combines:
- TF-IDF + cosine-similarity search
- Personalized ranking from previous searches, clicks, views and feedback
- Separate Education and Movies profiles
- AI-curated recommendations
- Tracked external learning/movie destinations

## Run in VS Code (CMD terminal)

```cmd
python -m venv venv
venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000

## External destinations

- Education results open a relevant YouTube learning search.
- Movie results open an IMDb title search.
- Clicking an external resource is logged as a click so the personalization model can learn.

## Keep previous activity

If you have an older AURAVIS/SeekMind database, copy its `database\app.db` into this project's `database\app.db` before running.

## Project structure

- `app.py` — Flask application and routes
- `search_engine.py` — TF-IDF search
- `user_profile.py` — personalization/recommendation engine
- `database.py` — SQLite activity and feedback
- `data/` — education and movie datasets
- `templates/` — UI pages
- `static/` — AURAVIS logo and styling
