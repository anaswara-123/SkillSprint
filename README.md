# SkillSprint – AI-Powered Interview Preparation Assistant

A Streamlit application for role-specific interview practice, LLM-based question generation, structured answer feedback, skill-gap recommendations and progress tracking.

## Stack
Python, Streamlit, Gemini API / Claude API, SQLite, Pandas and Plotly.

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create a virtual environment: `py -m venv .venv`
4. Activate it on Windows: `.venv\\Scripts\\activate`
5. Install: `pip install -r requirements.txt`
6. Copy `.env.example` to `.env` and add your own Gemini API key.
7. Run: `streamlit run app.py`

Select Gemini or Claude in the sidebar. Gemini is selected by default. Never commit `.env` or expose API keys. If the API is unavailable, the app loads clearly labelled demo questions and placeholder feedback; this is not live AI evaluation.

## Evaluation
The LLM assesses technical accuracy, relevance, completeness and clarity (each 0–10), then provides strengths, missing points, feedback and a suggested answer. SkillSprint converts the four dimensions into a 0–100 score. These scores are advisory, not an objective measure of interview success.

## Submission checklist
- [ ] Configure and test a real LLM API key.
- [ ] Complete a real AI-backed interview session.
- [ ] Test saved history and performance page.
- [ ] Capture screenshots of the working app.
- [ ] Record a live demo explaining the problem, workflow, AI integration and your contribution.
- [ ] Add genuine development commits to GitHub.
- [ ] Complete AI_USAGE_LOG.md honestly.
- [ ] Verify public repository and Google Drive demo access.

Do not claim that you trained an AI model. SkillSprint integrates an existing LLM. Review the generated code and be ready to explain and modify it.
