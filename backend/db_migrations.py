#!/usr/bin/env python3
"""
Database migration script for Echelon platform.
"""

import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os
from models import get_session, init_db, User, School, Job, File

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_tables():
    """Create database tables."""
    try:
        init_db()
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        return False

def seed_data():
    """Seed the database with initial data."""
    try:
        db = get_session()
        
        # Add a default school
        if db.query(School).filter(School.id == "chico-high-school").first() is None:
            school = School(
                id="chico-high-school",
                name="Chico High School",
                description="Chico High School, California",
                configuration={
                    "periods": ["R1", "R2", "R3", "R4", "G1", "G2", "G3", "G4"],
                    "special_courses": {
                        "Medical Career": ["R1", "G1"],
                        "Heroes Teach": ["R2", "G2"]
                    }
                }
            )
            db.add(school)
            logger.info("Added default school: Chico High School")
        
        # Add a test user
        if db.query(User).filter(User.email == "admin@example.com").first() is None:
            user = User(
                id="test-user-1",
                cognito_id="test-cognito-id",
                email="admin@example.com",
                name="Test Admin",
                role="Admin"
            )
            db.add(user)
            logger.info("Added test user: admin@example.com")
        
        db.commit()
        logger.info("Database seeded successfully")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {str(e)}")
        return False
    finally:
        db.close()

def drop_tables():
    """Drop all database tables."""
    try:
        # Get database URL from environment or use default
        db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/echelon')
        engine = create_engine(db_url)
        
        # Drop tables
        from models import Base
        Base.metadata.drop_all(engine)
        logger.info("Database tables dropped successfully")
        return True
    except Exception as e:
        logger.error(f"Error dropping database tables: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python db_migrations.py [create|seed|drop]")
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "create":
        success = create_tables()
    elif command == "seed":
        success = seed_data()
    elif command == "drop":
        success = drop_tables()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python db_migrations.py [create|seed|drop]")
        return 1
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())