from enum import Enum


class TaskTag(str, Enum):
    DEEP = "DEEP"               # 4 slot units = 100 minutes
    MODERATE = "MODERATE"       # 2 slot units = 50 minutes
    MECHANICAL = "MECHANICAL"   # 1 slot unit  = 25 minutes


class TaskStatus(str, Enum):
    PENDING = "PENDING"         # blocked by unmet dependencies
    AVAILABLE = "AVAILABLE"     # dependencies met, ready for pull
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"   # replaced by breakdown tasks


class MilestoneStatus(str, Enum):
    DRAFT = "DRAFT"
    STAGED = "STAGED"           # approved, waiting for capacity or epoch boundary
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class GoalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"         # terminal_deadline passed without completion


class EnergyLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SelfEfficacyLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"