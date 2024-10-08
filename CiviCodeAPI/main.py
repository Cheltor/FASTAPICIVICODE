from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from routes import addresses_router, users_router, businesses_router, contacts_router, violations_router, comments_router
from database import engine, Base
import uvicorn

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("App startup event")
    yield  # This will allow the app to run
    # Shutdown logic
    print("App shutdown event")

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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint for testing
@app.get("/")
def read_root():
    return {"message": "Welcome to the Address API"}

# Run the application (for development)
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
