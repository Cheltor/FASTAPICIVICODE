from docxtpl import DocxTemplate
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

def validate_template_category(content: bytes, category: str) -> bool:
    """
    Validates that a DOCX template is valid and can be rendered with a dummy context.

    Args:
        content (bytes): The raw file content.
        category (str): The category of the template ('violation', 'compliance', 'license').

    Returns:
        bool: True if valid.

    Raises:
        ValueError: If the file is not a valid DOCX or fails rendering.
    """

    try:
        file_stream = BytesIO(content)
        doc = DocxTemplate(file_stream)

        # Define superset of dummy data for all categories to ensure basic rendering works
        # This includes keys used in all 3 endpoints
        dummy_context = {
            "today": "01/01/2024",
            "combadd": "123 Main St",
            "premisezip": "12345",
            "ownername": "John Doe",
            "owneraddress": "456 Elm St",
            "ownercity": "Metropolis",
            "ownerstate": "NY",
            "ownerzip": "10001",
            "created_at": "01/01/2024",
            "deadline_date": "02/01/2024",
            "userphone": "555-0199",
            "username": "Inspector Gadget",
            "license_number": "LIC-12345",
            "date_issued": "01/01/2024",
            "expiration_date": "12/31/2024",
            "fiscal_year": "FY24",
            "conditions": "No loud noises.",
            "business_name": "Acme Corp",
            "business_address": "789 Ind Park",
            # List data
            "violation_codes": [
                {
                    "chapter": "1",
                    "section": "101",
                    "name": "Bad Paint",
                    "description": "Paint is peeling off."
                }
            ]
        }

        doc.render(dummy_context)
        return True
    except Exception as e:
        logger.error(f"Template validation failed: {type(e).__name__}: {e}", exc_info=True)
        # Return a sanitized error message
        raise ValueError("Invalid template file. Please ensure it is a valid .docx file and compatible with the selected category.")
