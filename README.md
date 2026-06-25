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
1. Push this repo to GitHub.
2. Create a Studio on [Lightning AI](https://lightning.ai) and create a new app.
3. In Studio, set the required Secrets / Environment Variables:
	- `DATABASE_URL` — your Supabase/Postgres connection string
	- `INFERENCE_PROVIDER=local` (if you will serve the model on Lightning)
	- `LOCAL_INFERENCE_URL` — the internal URL of the model serving endpoint (if applicable)
	- `LIGHTNING_ACCELERATOR=gpu` (ensure your Lightning plan gives GPU access)
	- Optionally `HF_TOKEN` if you still want Hugging Face fallback
4. Use the `backend/litserve_app.py` entrypoint for LitServe-based deployments (this script defaults to `LIGHTNING_ACCELERATOR=gpu`).
	- Run command in Studio: `python backend/litserve_app.py`
5. Alternatively, deploy the whole backend as a container (Dockerfile provided) and run model serving separately on Lightning or another GPU host. Point `LOCAL_INFERENCE_URL` to that host.

Notes:
- The application supports two inference modes: `hf` (Hugging Face hosted) and `local` (self/Lightning-hosted). Configure `INFERENCE_PROVIDER` in `.env` or Studio Secrets.
- When using Lightning GPU, prefer serving the model on the same Lightning workspace (or an internal endpoint) to avoid external inference costs and latency.
