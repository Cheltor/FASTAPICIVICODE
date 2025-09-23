import os

# Prefer DATABASE_URL (Heroku) or HEROKU_DATABASE_URL, else default to local dev
DATABASE_URL = (
	os.getenv("DATABASE_URL")
	or os.getenv("HEROKU_DATABASE_URL")
	or "postgresql://rchelton:password@localhost:5433/codeenforcement_development"
)
