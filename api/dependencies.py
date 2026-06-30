# PATH: stride_backend/api/dependencies.py
# DOMAIN: FastAPI dependency providers — wires module-level store/db singletons
# and agent instances into route handlers via Depends().

from __future__ import annotations

from agents.drafting_agent.agent import DraftingAgent
from agents.model_agent.executor import ModelAgentExecutor
from agents.smart_agent.agent import SmartAgent
from agents.task_decomposer.agent import TaskDecomposer
from core.config import settings
from core.execution.slot_allocator import SlotAllocator
from core.scheduling.scheduling_component import SchedulingComponent
from storage.db import distilled_db, goal_db, onboarding_db, raw_db
from storage.distilled_store import DistilledStore
from storage.goal_store import GoalStore
from storage.onboarding_store import OnboardingStore
from storage.raw_store import RawStore

# ── Store singletons ────────────────────────────────────────────────────────────
# Bare Depends() in route signatures cannot construct classes whose
# constructors require non-default arguments (TinyDB instance, LLM client).
# These provider functions supply those arguments explicitly, backed by the
# same module-level db singletons storage/db.py already exposes.

_raw_store = RawStore(db=raw_db)
_distilled_store = DistilledStore(db=distilled_db)
_goal_store = GoalStore(db=goal_db)
_onboarding_store = OnboardingStore(db=onboarding_db)


def get_raw_store() -> RawStore:
    return _raw_store


def get_distilled_store() -> DistilledStore:
    return _distilled_store


def get_goal_store() -> GoalStore:
    return _goal_store


def get_onboarding_store() -> OnboardingStore:
    return _onboarding_store


# ── Agent providers ─────────────────────────────────────────────────────────────
# Agents are constructed fresh per request since ChatOpenAI/ChatAnthropic
# clients are lightweight; this also keeps the LLM provider hot-swappable
# via settings without restarting the app.

def get_drafting_agent() -> DraftingAgent:
    return DraftingAgent(llm=settings.get_llm())


def get_smart_agent() -> SmartAgent:
    return SmartAgent(llm=settings.get_llm())


def get_task_decomposer() -> TaskDecomposer:
    return TaskDecomposer(llm=settings.get_llm())


def get_model_agent_executor() -> ModelAgentExecutor:
    return ModelAgentExecutor(
        raw_store=_raw_store,
        distilled_store=_distilled_store,
        goal_store=_goal_store,
        llm=settings.get_llm(),
    )


# ── Pure-Python component providers ─────────────────────────────────────────────

def get_scheduling_component() -> SchedulingComponent:
    return SchedulingComponent()


def get_slot_allocator() -> SlotAllocator:
    return SlotAllocator()