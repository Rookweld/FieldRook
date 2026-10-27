"""Technician's memory: verified resolution library (M009)."""

from app.knowledge.service import (
    KnowledgeBudgetError,
    KnowledgeError,
    fingerprint,
    match_entries,
    recheck_entry,
    record_entry,
)

__all__ = [
    "KnowledgeBudgetError",
    "KnowledgeError",
    "fingerprint",
    "match_entries",
    "recheck_entry",
    "record_entry",
]
