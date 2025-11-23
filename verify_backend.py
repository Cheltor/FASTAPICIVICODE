import sys
import os
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['google.generativeai.types'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.exc'] = MagicMock()
sys.modules['models'] = MagicMock()
sys.modules['fastapi'] = MagicMock()
sys.modules['pydantic'] = MagicMock()

# Add the parent directory to sys.path so we can import CiviCodeAPI
sys.path.append(r'c:\Users\ryanm\Desktop\CiviCode\FastAPI')

try:
    print("Attempting to import CiviCodeAPI.genai_client...")
    import CiviCodeAPI.genai_client
    print("Successfully imported CiviCodeAPI.genai_client")

    print("Attempting to import CiviCodeAPI.routes.assistant...")
    import CiviCodeAPI.routes.assistant
    print("Successfully imported CiviCodeAPI.routes.assistant")

    print("Backend verification successful: No import errors.")
except Exception as e:
    print(f"Backend verification failed: {e}")
    import traceback
    traceback.print_exc()

