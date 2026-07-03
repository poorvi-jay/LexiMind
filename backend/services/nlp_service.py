"""
NLP Service — Owner: M2
Handles grammar correction (F27), phonetic spell correction (F26),
and homophone detection (F28).

STATUS: Skeleton only.
- Grammar logic added in Task 2 (F27)
- Phonetic logic added in Task 3 (F26)
- Homophone logic added in Task 4 (F28)

Do not import heavy models here until the relevant task —
LanguageTool has a 10-15s JVM startup cost, so it must be loaded
once at module level, never per-request. This will be added in Task 2.
"""

# Model/tool loading (LanguageTool, spaCy) will go here in later tasks.