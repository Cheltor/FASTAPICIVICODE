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
from .dashboard import router as dashboard_router
from .permits import router as permits_router
from .sir import router as sir_router
from .notifications import router as notifications_router
from .assistant import router as assistant_router
from .settings import router as settings_router
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
    "dashboard_router",
    "permits_router",
    "sir_router",
    "notifications_router",
    "assistant_router",
    "settings_router",
    # Add other routers here
]
