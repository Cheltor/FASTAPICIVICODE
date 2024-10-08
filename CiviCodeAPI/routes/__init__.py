from .addresses import router as addresses_router
from .users import router as users_router
# Import other route modules as needed

# You can list all the routers here
__all__ = [
    "addresses_router",
    "users_router",
    # Add other routers here
]
