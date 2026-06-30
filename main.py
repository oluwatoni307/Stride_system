# PATH: stride_backend/main.py

from fastapi import FastAPI
from api.routes.goals import router as goals_router
from api.routes.tasks import router as tasks_router
from api.routes.weekly import router as weekly_router
from api.routes.schedule import router as schedule_router
from api.routes.onboarding import router as onboarding_router

app = FastAPI(title="Stride Backend", version="1.0.0")

app.include_router(goals_router)
app.include_router(tasks_router)
app.include_router(weekly_router)
app.include_router(schedule_router)
app.include_router(onboarding_router)


@app.get("/health")
def health():
    return {"status": "ok"}