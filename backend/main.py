from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import document, interview
from core.config import settings
from db.supabase_client import init_db

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()
    print("Application Startup Complete. Supabase is ready.")

app.include_router(document.router)
app.include_router(interview.router)

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
