# PATH: stride_backend/main.py

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles
import logging

log = logging.getLogger("stride_demo")

app = FastAPI(title="Stride Backend", version="1.0.0")

# Try to include the real routers; if any import fails (heavy deps),
# fall back to lightweight mock endpoints so the demo UI can run.
try:
    from api.routes.goals import router as goals_router
    from api.routes.tasks import router as tasks_router
    from api.routes.weekly import router as weekly_router
    from api.routes.schedule import router as schedule_router
    from api.routes.onboarding import router as onboarding_router

    app.include_router(goals_router)
    app.include_router(tasks_router)
    app.include_router(weekly_router)
    app.include_router(schedule_router)
    app.include_router(onboarding_router)
except Exception as e:
    # Log the error and register a small mock router for demo purposes
    log.exception("Failed to import real API routers; using mock demo routers: %s", e)

    mock = APIRouter()

    # In-memory demo state
    _demo_state: dict = {
        "last_pulled": {},    # user_id -> task dict
        "onboarding": {},     # user_id -> profile dict
    }

    @mock.post("/tasks/pull")
    async def demo_pull(payload: dict):
        user_id = payload.get("user_id", "demo-user")
        # Return a simple fake task so the UI can exercise completion flow
        task = {
            "task_id": "demo-task-1",
            "goal_id": "demo-goal-1",
            "milestone_id": "demo-milestone-1",
            "description": "Demo task: do something",
            "tag": "MECHANICAL",
        }
        _demo_state["last_pulled"][user_id] = task
        return {"pulled_task": task, "state_message": "mock: pulled demo task"}

    @mock.post("/tasks/complete")
    async def demo_complete(payload: dict):
        user_id = payload.get("user_id")
        task_id = payload.get("task_id")
        if not user_id or not task_id:
            raise HTTPException(status_code=400, detail="user_id and task_id required")
        last = _demo_state["last_pulled"].get(user_id)
        if not last or last.get("task_id") != task_id:
            return {"task_id": task_id, "success": False, "state": "NOT_FOUND_IN_DEMO"}
        # clear pulled
        _demo_state["last_pulled"][user_id] = None
        return {"task_id": task_id, "success": True, "state": "COMPLETED (demo)"}

    @mock.post("/weekly/cycle")
    async def demo_weekly(payload: dict):
        user_id = payload.get("user_id", "demo-user")
        week_start = payload.get("week_start")
        return {"user_id": user_id, "week_start": week_start, "result": "mock weekly cycle run"}

    @mock.get("/onboarding/profile/{user_id}")
    async def demo_get_profile(user_id: str):
        profile = _demo_state["onboarding"].get(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="profile not found (demo)")
        return profile

    @mock.post("/onboarding/profile")
    async def demo_create_profile(payload: dict):
        user_id = payload.get("user_id", "demo-user")
        _demo_state["onboarding"][user_id] = payload
        return {"success": True, "profile": payload}

    app.include_router(mock)

# Serve a small static UI demo at /ui (places ui files in repo/ui-demo)
app.mount("/ui", StaticFiles(directory="ui-demo", html=True), name="ui")


@app.get("/health")
def health():
    return {"status": "ok"}