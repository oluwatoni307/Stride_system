# PATH: stride_backend/storage/db.py
# DOMAIN: Opens and exposes the raw and distilled TinyDB instances at module level.
from __future__ import annotations
import os
from tinydb import TinyDB
from core.config import settings
# Ensure data directory exists before opening databases
os.makedirs(os.path.dirname(settings.tinydb_raw_store_path), exist_ok=True)
raw_db: TinyDB = TinyDB(settings.tinydb_raw_store_path)
distilled_db: TinyDB = TinyDB(settings.tinydb_distilled_store_path)
goal_db: TinyDB = TinyDB(settings.tinydb_goal_store_path)
onboarding_db: TinyDB = TinyDB(settings.tinydb_onboarding_store_path)