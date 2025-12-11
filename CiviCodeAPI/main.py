import os
import logging
from dotenv import load_dotenv

# Load environment variables before importing app modules that read them
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dev_env = os.path.join(ROOT, '.env.development')
if os.path.exists(dev_env):
    load_dotenv(dev_env)
else:
    # fallback to default .env
    load_dotenv(os.path.join(ROOT, '.env'))

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from routes import addresses_router, users_router, businesses_router, contacts_router, violations_router, comments_router, citations_router, inspections_router, codes_router, codes_sync_mvp_router, licenses_router, dashboard_router, permits_router, sir_router, notifications_router, assistant_router, settings_router, push_subscriptions_router, word_templates, templates, map # Updated import
from database import engine, Base
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logging.info("App startup event")
    yield
    # Shutdown logic
    logging.info("App shutdown event")


app = FastAPI(lifespan=lifespan)

# Create all the tables in the database (make sure models are imported)
Base.metadata.create_all(bind=engine)

# Include the address routes from routes.py
app.include_router(addresses_router)

# Include the user routes from routes.py
app.include_router(users_router)

# Include the business routes from routes.py
app.include_router(businesses_router)

# Include the contact routes from routes.py
app.include_router(contacts_router)

# Include the violation routes from routes.py
app.include_router(violations_router)

# Include the comment routes from routes.py
app.include_router(comments_router)

# Include the citation routes from routes.py
app.include_router(citations_router)

# Include the inspection routes from routes.py
app.include_router(inspections_router)

# Include the code routes from routes.py
app.include_router(codes_router)

# Include the code sync MVP routes
app.include_router(codes_sync_mvp_router)

# Include the license routes from routes.py
app.include_router(licenses_router)

# Include the dashboard routes from routes.py
app.include_router(dashboard_router)

# Include the permit routes from routes.py
app.include_router(permits_router)

# Include the word template routes from routes.py
app.include_router(word_templates.router)  # Registered the router

# Include SIR stats routes
app.include_router(sir_router)

# Include notifications routes
app.include_router(notifications_router)

# Include push subscription routes
app.include_router(push_subscriptions_router)

# Include assistant chat routes
app.include_router(assistant_router)

# Include settings routes
app.include_router(settings_router)

# Include template routes
app.include_router(templates.router)

# Include map routes
app.include_router(map.router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Expose X-Total-Count so the browser can read the total results header for pagination
    expose_headers=["X-Total-Count"],
)

# Root endpoint for testing
@app.get("/")
def read_root():
    return {"message": "Welcome to the Address API"}

# Run the application (for development)
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="debug")
