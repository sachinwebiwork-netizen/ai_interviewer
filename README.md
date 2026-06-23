# AI Interviewer

AI-powered technical interview platform. Upload resumes and job descriptions, then conduct personalized technical interviews with AI-generated questions, feedback, and hiring reports.

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** Supabase (PostgreSQL)
- **AI:** Hugging Face Inference API (Mistral-7B)
- **Deployment:** Lightning AI

## Project Structure

```
.
├── backend/
│   ├── api/routers/       # FastAPI route handlers
│   ├── core/              # Config & settings
│   ├── db/                # Database client (Supabase)
│   ├── schemas/           # Pydantic models
│   ├── services/          # Business logic & AI service
│   ├── main.py            # FastAPI app entrypoint
│   ├── server.py          # Uvicorn runner
│   ├── litserve_app.py    # LitServe wrapper for Lightning AI
│   ├── Dockerfile         # Container image
│   └── requirements.txt
├── frontend/              # (Coming soon)
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/document/upload` | Upload resume & JD |
| `POST` | `/interview/question` | Generate next question |
| `POST` | `/interview/feedback` | Evaluate answer |
| `POST` | `/interview/report` | Final hiring report |

## Quick Start

```bash
cd backend
pip install -r requirements.txt

# Set environment variables
export HF_TOKEN=your_huggingface_token
export DATABASE_URL=your_supabase_url

python server.py
```

## Deploy on Lightning AI

1. Push this repo to GitHub
2. Create a Studio on [Lightning AI](https://lightning.ai)
3. Set `HF_TOKEN` and `DATABASE_URL` in Studio Secrets
4. Run `python backend/server.py`

Or deploy as a container via AI Hub using the included `Dockerfile`.
