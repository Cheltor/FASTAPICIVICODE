import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from dotenv import load_dotenv

# Ensure we can import from the local directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import User, Violation, Inspection
from email_service import send_daily_digest_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    # Only run on weekdays (0=Mon, 4=Fri)
    if datetime.now().weekday() >= 5:
        logger.info("Today is a weekend. Skipping daily digest.")
        return

    logger.info("Starting daily digest email job.")
    db = SessionLocal()
    try:
        # 1. Find all users with role=1 (ONS)
        # Assuming role=1 is the correct role for neighborhood services/ONS based on user input
        users = db.query(User).filter(User.role == 1, User.active == True).all()
        logger.info(f"Found {len(users)} ONS users.")

        for user in users:
            logger.info(f"Processing user {user.email} (ID: {user.id})")

            # 2. Fetch Open Violations
            # Status 0 = Open
            violations = (
                db.query(Violation)
                .options(joinedload(Violation.address))
                .filter(Violation.user_id == user.id, Violation.status == 0)
                .all()
            )

            # 3. Fetch Pending Inspections (not 'completed', 'satisfactory', 'closed')
            # Source != 'Complaint'
            # Inspector is the user
            closed_statuses = ["completed", "satisfactory", "closed", "resolved", "no violation found"]
            inspections = (
                db.query(Inspection)
                .options(joinedload(Inspection.address))
                .filter(
                    Inspection.inspector_id == user.id,
                    Inspection.source != 'Complaint'
                )
                .all()
            )
            # Filter out closed statuses case-insensitively in Python if needed or rely on lower() in SQL
            # Let's filter in python to be safe with casing if the DB collation isn't clear
            inspections = [
                i for i in inspections
                if str(i.status).lower() not in closed_statuses
            ]

            # 4. Fetch Active Complaints
            # Source == 'Complaint'
            complaints = (
                db.query(Inspection)
                .options(joinedload(Inspection.address))
                .filter(
                    Inspection.inspector_id == user.id,
                    Inspection.source == 'Complaint'
                )
                .all()
            )
            complaints = [
                c for c in complaints
                if str(c.status).lower() not in closed_statuses
            ]

            # Check if there is anything to send
            if not violations and not inspections and not complaints:
                logger.info(f"User {user.email} has no open items. Skipping.")
                continue

            logger.info(f"User {user.email}: {len(violations)} violations, {len(inspections)} inspections, {len(complaints)} complaints.")

            # 5. Send Email
            if user.email:
                success = send_daily_digest_email(
                    to_email=user.email,
                    violations=violations,
                    inspections=inspections,
                    complaints=complaints
                )
                if success:
                    logger.info(f"Successfully sent digest to {user.email}")
                else:
                    logger.error(f"Failed to send digest to {user.email}")
            else:
                logger.warning(f"User {user.id} has no email address.")

    except Exception as e:
        logger.exception("Error running daily digest job")
    finally:
        db.close()
        logger.info("Daily digest job finished.")

if __name__ == "__main__":
    main()
