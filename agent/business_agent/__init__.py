"""A roster-optimising business agent that drafts, and never sends.

Pipeline: read messages -> triage into events -> fold into roster ->
find gaps -> rank replacements -> draft the asks -> write a brief.
"""

__version__ = "0.1.0"
