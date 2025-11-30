"""
Configuration module for CiviCodeAPI.

This module handles environment configuration and global constants.
"""

import os

# Prefer DATABASE_URL (Heroku) or HEROKU_DATABASE_URL, else default to local dev
DATABASE_URL = (
	os.getenv("DATABASE_URL")
	or os.getenv("HEROKU_DATABASE_URL")
	or "postgresql://rchelton:password@localhost:5433/codeenforcement_development"
)
"""
str: The database connection URL.

Prioritizes `DATABASE_URL`, then `HEROKU_DATABASE_URL`, and defaults to a local
PostgreSQL development database if neither is set.
"""
