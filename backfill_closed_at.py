import sys
import os
from datetime import datetime

# Add CiviCodeAPI to path so we can import database and models
sys.path.append(os.path.join(os.path.dirname(__file__), 'CiviCodeAPI'))

from database import SessionLocal
from models import Violation

def backfill_closed_at():
    db = SessionLocal()
    try:
        # Find closed violations (status=1) with no closed_at
        violations = db.query(Violation).filter(Violation.status == 1, Violation.closed_at == None).all()
        print(f"Found {len(violations)} closed violations to update.")
        
        count = 0
        for v in violations:
            # Use updated_at as a proxy for closed_at
            v.closed_at = v.updated_at
            count += 1
            
        db.commit()
        print(f"Successfully updated {count} violations.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    backfill_closed_at()
