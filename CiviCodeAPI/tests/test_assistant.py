from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from CiviCodeAPI.main import app
from CiviCodeAPI.models import Code, User
from CiviCodeAPI.database import get_db
from CiviCodeAPI.routes.auth import get_current_user
import pytest

# This fixture will be used to override the get_db dependency in the test
@pytest.fixture
def mock_db_session():
    db = MagicMock()
    yield db

# This fixture will be used to override the get_current_user dependency in the test
@pytest.fixture
def mock_current_user():
    return User(id=1, email="test@example.com", role=3)

# This is the main test function
@patch('CiviCodeAPI.routes.assistant.run_assistant', new_callable=AsyncMock)
def test_create_assistant_chat_with_code_citation(mock_run_assistant, mock_db_session, mock_current_user, monkeypatch):
    # Set the OpenAI environment variables
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("OPENAI_ASSISTANT_ID", "test_assistant_id")
    # We use FastAPI's dependency_overrides to replace the actual dependencies
    # with our mocks for the duration of this test.
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    client = TestClient(app)

    # We also patch the `search_codes` function to control its output
    with patch('CiviCodeAPI.routes.assistant.search_codes') as mock_search_codes:
        # Set up the mock return values
        mock_code = Code(id=1, chapter="10", section="20A", name="Weed Abatement", description="This is a test code.")
        mock_search_codes.return_value = [mock_code]
        mock_run_assistant.return_value = ("The maximum allowed height for weeds is 12 inches. [10.20A - Weed Abatement]", "thread_123")

        # Make the request to the endpoint
        response = client.post("/chat", json={"message": "What's the maximum allowed height for weeds?"})

        # Assert the response
        assert response.status_code == 200
        assert response.json() == {"reply": "The maximum allowed height for weeds is 12 inches. [10.20A - Weed Abatement]", "threadId": "thread_123"}

        # Assert that the mocks were called correctly
        mock_search_codes.assert_called_once_with(mock_db_session, "What's the maximum allowed height for weeds?")
        mock_run_assistant.assert_called_once_with("What's the maximum allowed height for weeds?", None, [mock_code])

    # Clean up the dependency overrides after the test is done
    app.dependency_overrides = {}
