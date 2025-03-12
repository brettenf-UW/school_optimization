from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import boto3
import json
from sqlalchemy.pool import NullPool

# Base class for all models
Base = declarative_base()

# Import all models
from .user import User
from .school import School
from .job import Job
from .file import File
from .optimization_model import OptimizationModel
from .audit_log import AuditLog

def get_database_url():
    """
    Get the database URL from Secrets Manager
    """
    environment = os.environ.get("ENVIRONMENT", "dev")
    secret_arn = os.environ.get("DATABASE_SECRET_ARN")
    
    if not secret_arn:
        # Local development fallback
        return "postgresql://postgres:postgres@localhost:5432/echelon"
    
    try:
        secrets_client = boto3.client("secretsmanager")
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        db_secrets = json.loads(response["SecretString"])
        
        return f"postgresql://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['dbname']}"
    except Exception as e:
        # Log the error and fallback to local development
        print(f"Error getting database URL from Secrets Manager: {str(e)}")
        return "postgresql://postgres:postgres@localhost:5432/echelon"

def get_engine():
    """
    Get a database engine
    """
    # Using NullPool to avoid connection pooling issues in serverless environments
    return create_engine(get_database_url(), poolclass=NullPool)

def get_session():
    """
    Get a database session
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    """
    Initialize the database
    """
    engine = get_engine()
    Base.metadata.create_all(engine)