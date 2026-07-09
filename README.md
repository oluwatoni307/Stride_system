# Stride Backend

An AI-powered goal coaching system. Stride helps users set meaningful goals, break them into executable task graphs, and schedule work intelligently across their week — without over-relying on AI for things deterministic code handles better.

---

## Core Philosophy

**LLMs Classify. Deterministic Code Calculates.**

- AI is used for three things only: decomposing goals into structure, assessing viability, and generating weekly reflection.
- Scheduling, slot allocation, weight calculation, dependency resolution, and state management are all pure Python.
- The more conventions the system enforces, the fewer agent calls it needs.

---

## Architecture Overview

```
Raw Goal Text
     │
     ▼
DraftingAgent          → objectives, milestones, success metrics
     │
     ▼
SmartAgent             → SMART formulation, impact score, deadline
     │
     ▼
TaskDecomposer         → task graph per milestone (tags + dependencies)
     │
     ▼
SchedulingComponent    → DEEP session plans per milestone (deterministic)
     │
     ▼
SlotAllocator          → real-time task pull engine (two-tier priority)
     │
     ▼
ModelAgentExecutor     → weekly guidance, edit negotiation, sole DB writer
```

---

## Key Concepts

### Tri-Vector Weighting
Every milestone gets a weight derived from three variables:
- **I** — Impact Score (1–5), inherited from parent Goal's `macro_impact`, assigned by SmartAgent
- **U** — Urgency Multiplier, computed by Python from `terminal_deadline`
- **V** — Volume Density, computed from the task graph slot cost

```
W_raw = I × U × V
W_normalized = W_raw / Σ(all active milestone W_raw)
```

### Execution Corridor
Each milestone gets a weekly slot budget:
```
weekly_units = round(max_workable_hours × 2.4)   # 1 unit = 25 minutes
min_weekly_units = round(W_normalized × weekly_units × 0.6)   # floor
max_weekly_units = round(W_normalized × weekly_units × 1.0)   # ceiling
```

### Two-Tier Pull Logic
When a user requests the next task:
1. **Tier 1 (Safety Net):** If any milestone is below its floor, pull from the most starved one first.
2. **Tier 2 (Growth Phase):** Once all milestones hit their floor, pull from the one furthest from its ceiling.

### Biological Refractory Rules
- After a DEEP task: next pull cannot be DEEP (global lockout)
- After a DEEP task: next pull must come from a different milestone (forced rotation)
- After 2 consecutive pulls from the same milestone: forced rotation

### Slot Units
```
MECHANICAL = 1 unit  = 25 minutes
MODERATE   = 2 units = 50 minutes
DEEP       = 4 units = 100 minutes
```

---

## Project Structure

```
stride_backend/
├── agents/
│   ├── drafting_agent/       # DraftingAgent — goal decomposition
│   ├── smart_agent/          # SmartAgent — SMART formulation + impact score
│   ├── task_decomposer/      # TaskDecomposer — task graph generation
│   └── model_agent/          # ModelAgentExecutor — edits, guidance, distillation
├── api/
│   ├── dependencies.py       # FastAPI dependency providers
│   └── routes/
│       ├── goals.py          # /goals — draft, structure, confirm
│       ├── tasks.py          # /tasks — pull, complete
│       ├── weekly.py         # /weekly — cycle (guidance + distillation)
│       └── schedule.py       # /schedule — slot allocation
├── core/
│   ├── config.py             # Settings + all constants
│   ├── execution/
│   │   └── slot_allocator.py # Real-time task pull engine
│   ├── feedback/
│   │   └── feedback_loop.py  # Event packager (no LLM)
│   ├── scheduling/
│   │   └── scheduling_component.py  # DEEP session planner (no LLM)
│   └── schemas/
│       ├── entities.py       # Goal, Milestone, Task, FeedbackEvent, etc.
│       ├── enums.py          # TaskTag, TaskStatus, MilestoneStatus, etc.
│       └── contracts/        # Boundary schemas for all agent I/O
├── storage/
│   ├── db.py                 # TinyDB instances
│   ├── raw_store.py          # FeedbackEvents, PhaseTransitions
│   ├── distilled_store.py    # DistilledModel, PriorityList
│   └── goal_store.py         # Goals, Milestones, Tasks
├── tests/                    # 77 tests, all passing
├── main.py                   # FastAPI app entry point
└── .env                      # LLM provider config
```

---

## API Routes

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/goals/draft` | DraftingAgent converts raw text to structured draft |
| POST | `/goals/draft/revise` | DraftingAgent revises draft on user feedback |
| POST | `/goals/structure` | SmartAgent fits draft to user context |
| POST | `/goals/structure/negotiate` | SmartAgent negotiates on pushback |
| POST | `/goals/confirm` | Writes Goal + Milestones + Tasks, runs scheduling |
| POST | `/tasks/pull` | SlotAllocator returns next task based on energy + state |
| POST | `/tasks/complete` | Marks task complete, unlocks dependent tasks |
| POST | `/weekly/cycle` | Aggregates week data, generates guidance, resets state |
| POST | `/schedule/allocate` | SchedulingComponent assigns DEEP session days |
| GET  | `/health` | Health check |

---

## Setup

**Requirements:** Python 3.12+

```bash
# Install dependencies
pip install fastapi uvicorn tinydb pydantic python-dotenv \
            langchain langchain-core langchain-google-genai \
            anyio httpx pytest pytest-asyncio

# Configure environment
cp .env.example .env
# Set GOOGLE_API_KEY, LLM_PROVIDER=gemini, LLM_MODEL=gemini-1.5-flash

# Run server
uvicorn main:app --reload

# Run tests
python -m pytest tests/ -v
```

---

## Environment Variables

```
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-flash
GOOGLE_API_KEY=your-key-here
TINYDB_RAW_STORE_PATH=data/raw_store.json
TINYDB_DISTILLED_STORE_PATH=data/distilled_store.json
TINYDB_GOAL_STORE_PATH=data/goal_store.json
```

---

## Agent Responsibilities

| Agent | Owns | Never does |
|-------|------|------------|
| DraftingAgent | Raw goal → objectives, milestones, metrics | SMART formulation, capacity assessment |
| SmartAgent | Fits draft to context, assigns I + deadline | Goal decomposition, weight calculation |
| TaskDecomposer | Task graph per milestone, stagnation breakdown | Scheduling, slot assignment |
| ModelAgentExecutor | Weekly guidance, edit negotiation, sole DB writer | Goal creation, task generation |
| SchedulingComponent | DEEP session day planning (deterministic) | LLM calls, storage |
| SlotAllocator | Real-time task pull with two-tier priority (deterministic) | LLM calls, storage |
| FeedbackLoop | Package task completion events (pure data) | LLM calls, storage, intelligence |

---

## Storage Write Ownership

Only `ModelAgentExecutor` writes to storage. No agent imports a store class directly. All context arrives via typed boundary inputs.

```
RawStore       ← ModelAgentExecutor only
DistilledStore ← ModelAgentExecutor only
GoalStore      ← ModelAgentExecutor only
```

---

## Test Suite

```
tests/test_drafting_agent.py        12 tests
tests/test_feedback_loop.py          8 tests
tests/test_goal_routes.py            6 tests
tests/test_schedule_route.py         7 tests
tests/test_scheduling_component.py  17 tests
tests/test_task_decomposer.py       15 tests
tests/test_task_routes.py            7 tests
tests/test_weekly_route.py           5 tests
─────────────────────────────────────────────
TOTAL                               77/77 passing
```

All agent tests use `RunnableLambda` mocks — not bare `AsyncMock` — to correctly simulate LangChain chain behaviour.
