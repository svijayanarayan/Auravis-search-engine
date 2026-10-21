# AURAVIS — public deployment package

This package is prepared for deployment on Render.

## Deploy
1. Create/sign in to GitHub and create a **private** repository named `auravis-search`.
2. Upload the contents of this ZIP to the repository (not the ZIP itself).
3. Sign in to Render and choose **New → Blueprint**; connect the repository and apply `render.yaml`.
4. When prompted, add `OPENAI_API_KEY` only if you want Image Search's OpenAI vision feature. Do not put the key in source code or commit a `.env` file.
5. Wait for the build and open the `onrender.com` URL Render provides.

## Included deployment adjustments
- Excluded the local Windows `venv/` folder so the cloud installs its own dependencies.
- Added Gunicorn and Render configuration.
- Configured Flask to bind to the cloud-provided port.
- Reads the Flask session secret from `AURAVIS_SECRET_KEY`.
- Keeps the local CSV search independent of any API key.
- Configures image search to use OpenAI vision in production; this requires your own API key and may incur API charges.

## Important limitations
- Render's free web service filesystem is ephemeral. SQLite accounts, search history, and feedback can be reset on redeploy/restart. For persistent user data, configure a persistent disk on a paid service or move SQLite to a managed database such as PostgreSQL and update the app.
- The included CSV has 1,500 education rows and the bundled movie dataset is smaller; `prepare_movies_1000.py` is a local preparation script and is not run during deployment.
- Offline vision (`transformers`/`torch`) is not installed in this lightweight cloud build because those dependencies make the deployment very large. Image understanding is available when `OPENAI_API_KEY` is configured.
- Test login/register, searches, likes, profile, external resource links and image search after deployment.

## Local development
Install from `requirements.txt`, then run `python app.py`. For offline vision locally, install the extra packages from the original requirements and download the model separately.
