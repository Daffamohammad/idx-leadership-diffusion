"""Evidence builder.

Builds structured evidence objects for each group that can be consumed
by the UI and (later) an LLM narration layer.
"""
from .builder import build_group_evidence, build_evidence_table

__all__ = ["build_group_evidence", "build_evidence_table"]
