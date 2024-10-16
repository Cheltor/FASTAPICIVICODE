from .addresses import router as addresses_router
from .users import router as users_router
from .businesses import router as businesses_router
from .contacts import router as contacts_router
from .violations import router as violations_router
from .comments import router as comments_router
from .citations import router as citations_router
from .inspections import router as inspections_router
from .codes import router as codes_router
from .licenses import router as licenses_router
# Import other route modules as needed

# You can list all the routers here
__all__ = [
    "addresses_router",
    "users_router",
    "businesses_router",
    "contacts_router",
    "violations_router",
    "comments_router",
    "citations_router",
    "inspections_router",
    "codes_router",
    "licenses_router",
    # Add other routers here
]
