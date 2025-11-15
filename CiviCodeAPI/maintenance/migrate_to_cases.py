import os
import sys
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from CiviCodeAPI.models import Violation, Inspection, Case
from CiviCodeAPI.database import _database_url

def migrate_to_cases():
    """
    Migrates existing violations and inspections to the new cases model.
    """
    db_url = _database_url()
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        violations = db.query(Violation).filter(Violation.case_id.is_(None)).all()
        for violation in violations:
            case_number = f"V-{violation.id}"
            existing_case = db.query(Case).filter_by(case_number=case_number).first()
            if not existing_case:
                case = Case(
                    address_id=violation.address_id,
                    user_id=violation.user_id,
                    status="Violation Confirmed",
                    case_number=case_number
                )
                db.add(case)
                db.flush()
                violation.case_id = case.id

        inspections = db.query(Inspection).filter(Inspection.case_id.is_(None)).all()
        for inspection in inspections:
            case_number = f"I-{inspection.id}"
            existing_case = db.query(Case).filter_by(case_number=case_number).first()
            if not existing_case:
                case = Case(
                    address_id=inspection.address_id,
                    user_id=inspection.inspector_id,
                    status="Received",
                    case_number=case_number
                )
                db.add(case)
                db.flush()
                inspection.case_id = case.id

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate_to_cases()
