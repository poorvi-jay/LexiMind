"""
TEMPORARY DATABASE MODELS — Owner: M2
====================================
This file is a STOPGAP, not the final schema.

Per Build Guide Section 0.2: no SQLAlchemy models, no Alembic
migrations, and no `users` table exist in the repo yet. This file
will hold a minimal `users` table (email, password hash, pref_*
columns) so Authentication isn't blocked while waiting for the
real 6-table schema (PRD Section 4).

When the full schema lands, this file's `User` model gets merged
into it and this file is deleted. Do not build permanent
functionality on top of it without expecting that migration.

STATUS: Empty. Populated in the Auth phase (Task ~14).
"""

# SQLAlchemy Base and User model will be defined here later.