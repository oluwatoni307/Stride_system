# PATH: stride_backend/core/config.py
# DOMAIN: Application configuration — loads environment variables and exposes a settings instance.

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.tinydb_raw_store_path: str = os.environ.get(
            "TINYDB_RAW_STORE_PATH", "data/raw_store.json"
        )
        self.tinydb_distilled_store_path: str = os.environ.get(
            "TINYDB_DISTILLED_STORE_PATH", "data/distilled_store.json"
        )
        self.tinydb_goal_store_path: str = os.environ.get(
            "TINYDB_GOAL_STORE_PATH", "data/goal_store.json"
        )
        self.tinydb_onboarding_store_path: str = os.environ.get(
            "TINYDB_ONBOARDING_STORE_PATH", "data/onboarding_store.json"
        )
        self.llm_provider: str = os.environ.get("LLM_PROVIDER", "openai")
        self.llm_model: str = os.environ.get("LLM_MODEL", "gpt-4o")
        self.llm_max_tokens: int = int(os.environ.get("LLM_MAX_TOKENS", "1000"))
        self.openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
        self.anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

    def get_llm(self):
        if self.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.llm_model,
                max_tokens=self.llm_max_tokens,
                api_key=self.openai_api_key,
            )
        if self.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.llm_model,
                max_tokens=self.llm_max_tokens,
                api_key=self.anthropic_api_key,
            )
            
        if self.llm_provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.llm_model,
                google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
            )
        raise ValueError(f"Unsupported LLM provider: {self.llm_provider!r}")


settings = Settings()


# ─────────────────────────────────────────────
# SLOT CONSTANTS
# ─────────────────────────────────────────────
from core.schemas.enums import TaskTag

SLOT_DURATION_MINUTES = 25          # base unit: 1 slot = 25 minutes

SLOT_UNIT_CONSTANTS = {
    TaskTag.MECHANICAL: 1,          # 25 minutes
    TaskTag.MODERATE:   2,          # 50 minutes
    TaskTag.DEEP:       4,          # 100 minutes
}

# ─────────────────────────────────────────────
# EXECUTION ENGINE CONSTANTS
# ─────────────────────────────────────────────
MAX_CONSECUTIVE_PULLS   = 2         # before forced milestone rotation (MODERATE/MECHANICAL)
DEEP_LOCKOUT_SENTINEL   = 99        # consecutive_pull_count sentinel that forces rotation
STALL_THRESHOLD_DAYS    = 7         # days AVAILABLE before stalled_flag set on DEEP task
FLOOR_FACTOR            = 0.6       # min_weekly = normalized_weight × weekly_units × FLOOR_FACTOR

# ─────────────────────────────────────────────
# SCHEDULING CONSTANTS
# ─────────────────────────────────────────────
DEEP_MIN_GAP_DAYS       = 2         # minimum days between DEEP sessions per milestone

# ─────────────────────────────────────────────
# TRI-VECTOR URGENCY BRACKETS
# ─────────────────────────────────────────────
URGENCY_BRACKETS = [
    (7,  2.0),      # < 7 days remaining  → U = 2.0
    (30, 1.5),      # < 30 days remaining → U = 1.5
    (90, 1.2),      # < 90 days remaining → U = 1.2
    (float('inf'), 1.0),    # >= 90 days → U = 1.0
]