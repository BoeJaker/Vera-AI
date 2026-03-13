"""
Vera EventBus Configuration
"""

# Redis
REDIS_URL = "redis://localhost:6379"
STREAM_EVENTS = "vera:events"
STREAM_PRIORITY = "vera:events:priority"
STREAM_DLQ = "vera:events:dlq"
CONSUMER_GROUP = "vera-consumers"

# Retry
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2

# Postgres
POSTGRES_DSN = "postgresql://postgres:password@localhost:5432/vera"

# Memory promotion — event types that are candidates for HybridMemory
# Patterns use fnmatch syntax.  Only events matching at least one pattern
# are passed to the MemoryPromoter for scoring.
MEMORY_CANDIDATE_PATTERNS = [
    "memory.*",
    "llm.complete",
    "tool.complete",
    "task.complete",
    "agent.*",
    "focus.*",
    "orchestrator.task.*",
    "system.alert.*",
]

# Minimum promotion score (0.0-1.0) for an event to become a memory
MEMORY_PROMOTION_THRESHOLD = 0.5