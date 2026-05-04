from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import questions, quiz
from app.routers import reports

app = FastAPI(
    title="Quiz Auto-Evaluation Backend",
    description="Hexaware AI-Based Learning Platform - Pod 2",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

app.include_router(questions.router)
app.include_router(quiz.router)
app.include_router(reports.router)
