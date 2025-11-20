import sys
import os
import json

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from genai_client import search_codes

def test_search_codes():
    db = SessionLocal()
    try:
        # Test with a generic query
        query = "noise"
        print(f"Searching for: {query}")
        result = search_codes(db, query)
        print("Result:")
        print(result)
        
        data = json.loads(result)
        if isinstance(data, list) and len(data) > 0:
            print("✅ Search returned results.")
        else:
            print("⚠️ Search returned no results (might be expected if DB is empty).")

        # Test with a specific code if known, or just verify structure
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if "id" in first and "name" in first:
                 print("✅ Result structure is correct.")
            else:
                 print("❌ Result structure is incorrect.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_search_codes()
