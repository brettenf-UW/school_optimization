from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional, Dict, Any
from datetime import datetime
import boto3
import os
import json
import uuid
import logging
import jwt
from mangum import Mangum
import pandas as pd
from sqlalchemy.orm import Session
from models import get_session, init_db, User, School, Job, File, OptimizationModel, AuditLog

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Echelon Optimization Platform API",
    description="API for school scheduling optimization with Gurobi solver",
    version="1.0.0"
)

# CORS configuration to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AWS services
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
cognito_client = boto3.client('cognito-idp')

# Configuration
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'echelon-uploads')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', 'https://sqs.us-west-2.amazonaws.com/your-account-id/echelon-jobs')
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', 'us-west-2_gVCuWb3dQ')
COGNITO_APP_CLIENT_ID = os.environ.get('COGNITO_APP_CLIENT_ID', '2vabalt8ij3kfp4tibhahce7ds')

# OAuth2 scheme for token validation
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize database
@app.on_event("startup")
async def startup_db_client():
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")

# Dependency for database session
def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

# Authentication and Authorization
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        # Decode JWT token to get user claims
        # In production, this should validate the token signature with AWS Cognito public keys
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Get user from database
        user = db.query(User).filter(User.cognito_id == decoded["sub"]).first()
        
        if not user:
            # Create user if not exists (for development purposes)
            user = User(
                id=str(uuid.uuid4()),
                cognito_id=decoded["sub"],
                email=decoded.get("email", "unknown@example.com"),
                name=decoded.get("name", "Unknown User"),
                role=decoded.get("custom:role", "User")
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
        return user
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

async def verify_admin_access(user: User = Depends(get_current_user)):
    if user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# File Upload Endpoints
@app.post("/api/upload/school-data", status_code=201)
async def upload_school_data(
    background_tasks: BackgroundTasks,
    school_id: str = Form(...),
    sections_file: UploadFile = File(None),
    students_file: UploadFile = File(None),
    teachers_file: UploadFile = File(None),
    preferences_file: UploadFile = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload school data files for optimization
    """
    try:
        # Verify school exists
        school = db.query(School).filter(School.id == school_id).first()
        if not school:
            raise HTTPException(status_code=404, detail=f"School with ID {school_id} not found")
        
        # Create a unique folder for this school's uploads
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_key = f"{school_id}/uploads/{timestamp}/"
        
        # Dictionary to track uploaded files
        uploaded_files = {}
        db_files = []
        
        # Process each file if provided
        file_map = {
            "sections": sections_file,
            "students": students_file, 
            "teachers": teachers_file,
            "preferences": preferences_file
        }
        
        for file_type, file_obj in file_map.items():
            if file_obj and file_obj.filename:
                # Upload file to S3
                file_content = await file_obj.read()
                file_key = f"{folder_key}{file_type}/{file_obj.filename}"
                
                s3_client.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=file_key,
                    Body=file_content
                )
                
                uploaded_files[file_type] = file_key
                
                # Create file record in database
                db_file = File(
                    id=str(uuid.uuid4()),
                    name=file_obj.filename,
                    file_type=file_type,
                    s3_key=file_key,
                    content_type=file_obj.content_type,
                    size=len(file_content),
                    is_input=True,
                    validation_status="PENDING",
                    user_id=user.id,
                    school_id=school_id
                )
                db_files.append(db_file)
                db.add(db_file)
                
                # Basic validation in background
                background_tasks.add_task(validate_csv_file, file_content, file_type, db_file.id)
        
        # Create a metadata file for this upload
        metadata = {
            "school_id": school_id,
            "timestamp": timestamp,
            "uploaded_by": user.id,
            "files": uploaded_files
        }
        
        metadata_key = f"{folder_key}metadata.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=metadata_key,
            Body=json.dumps(metadata),
            ContentType="application/json"
        )
        
        # Log the upload event
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            event_type="UPLOAD",
            resource_type="FILE",
            description=f"Uploaded {len(db_files)} files for school {school_id}",
            details={"file_types": list(uploaded_files.keys())},
            user_id=user.id
        )
        db.add(audit_log)
        
        # Commit all database changes
        db.commit()
        
        return {
            "message": "Files uploaded successfully",
            "upload_id": timestamp,
            "files": uploaded_files,
            "file_ids": [file.id for file in db_files]
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading files: {str(e)}")

# Job Management Endpoints
@app.post("/api/jobs/schedule", status_code=201)
async def schedule_optimization_job(
    job_data: Dict[str, Any],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Schedule a new optimization job
    """
    try:
        # Verify school exists
        school = db.query(School).filter(School.id == job_data.get("school_id")).first()
        if not school:
            raise HTTPException(status_code=404, detail=f"School with ID {job_data.get('school_id')} not found")
        
        # Verify optimization model exists
        model = None
        if "model_id" in job_data and job_data["model_id"]:
            model = db.query(OptimizationModel).filter(OptimizationModel.id == job_data["model_id"]).first()
            if not model:
                raise HTTPException(status_code=404, detail=f"Optimization model with ID {job_data['model_id']} not found")
        
        # Create job in database
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            name=job_data.get("name", f"Job {job_id}"),
            job_type=job_data["job_type"],
            status="PENDING",
            parameters=job_data.get("parameters", {}),
            user_id=user.id,
            school_id=job_data["school_id"],
            model_id=model.id if model else None
        )
        db.add(job)
        
        # Associate files with the job if provided
        if "file_ids" in job_data and job_data["file_ids"]:
            files = db.query(File).filter(File.id.in_(job_data["file_ids"])).all()
            for file in files:
                file.job_id = job_id
        
        # Send job to SQS queue
        sqs_message = {
            "job_id": job_id,
            "school_id": job_data["school_id"],
            "job_type": job_data["job_type"],
            "parameters": job_data.get("parameters", {}),
            "model_id": model.id if model else None,
            "created_by": user.id
        }
        
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(sqs_message),
            MessageAttributes={
                'JobType': {
                    'DataType': 'String',
                    'StringValue': job_data["job_type"]
                },
                'SchoolId': {
                    'DataType': 'String',
                    'StringValue': job_data["school_id"]
                }
            }
        )
        
        # Update job status to QUEUED
        job.status = "QUEUED"
        
        # Log the job creation event
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            event_type="CREATE",
            resource_type="JOB",
            resource_id=job_id,
            description=f"Created optimization job {job.name}",
            details={"job_type": job_data["job_type"]},
            user_id=user.id
        )
        db.add(audit_log)
        
        # Commit all database changes
        db.commit()
        
        return {
            "message": "Job scheduled successfully",
            "job_id": job_id,
            "status": "QUEUED"
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error scheduling job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error scheduling job: {str(e)}")

@app.get("/api/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the status of an optimization job
    """
    try:
        # Get job from database
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
        
        # Check if user has access to the job (admin or job creator)
        if user.role != "Admin" and job.user_id != user.id:
            raise HTTPException(status_code=403, detail="You don't have access to this job")
        
        return {
            "job_id": job.id,
            "name": job.name,
            "status": job.status,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "school_id": job.school_id,
            "user_id": job.user_id
        }
            
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting job status: {str(e)}")

@app.get("/api/jobs/{job_id}/results")
async def get_job_results(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the results of a completed optimization job
    """
    try:
        # Get job from database
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
        
        # Check if user has access to the job (admin or job creator)
        if user.role != "Admin" and job.user_id != user.id:
            raise HTTPException(status_code=403, detail="You don't have access to this job")
        
        # Check if job is completed
        if job.status != "COMPLETED":
            raise HTTPException(status_code=400, detail=f"Job {job_id} is not completed yet. Current status: {job.status}")
        
        # Get result files
        result_files = db.query(File).filter(File.job_id == job_id, File.is_input == False).all()
        
        # Generate presigned URLs for result files
        file_downloads = []
        for file in result_files:
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': S3_BUCKET_NAME,
                    'Key': file.s3_key
                },
                ExpiresIn=3600  # URL valid for 1 hour
            )
            file_downloads.append({
                "file_id": file.id,
                "name": file.name,
                "file_type": file.file_type,
                "download_url": presigned_url
            })
        
        return {
            "job_id": job.id,
            "name": job.name,
            "status": job.status,
            "result_summary": job.result_summary,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "execution_time": job.execution_time,
            "files": file_downloads
        }
                
    except Exception as e:
        logger.error(f"Error getting job results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting job results: {str(e)}")

# Admin Endpoints
@app.get("/api/admin/jobs", dependencies=[Depends(verify_admin_access)])
async def list_all_jobs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to list all jobs across all schools
    """
    try:
        # Build query
        query = db.query(Job)
        
        # Apply filters
        if status:
            query = query.filter(Job.status == status)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        query = query.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        
        # Execute query
        jobs = query.all()
        
        return {
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "job_type": job.job_type,
                    "status": job.status,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "school_id": job.school_id,
                    "user_id": job.user_id
                }
                for job in jobs
            ],
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing jobs: {str(e)}")

@app.post("/api/admin/users")
async def create_user(
    user_data: Dict[str, Any],
    admin: User = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to create a new user
    """
    try:
        # Create user in Cognito
        cognito_response = cognito_client.admin_create_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=user_data["email"],
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': user_data["email"]
                },
                {
                    'Name': 'email_verified',
                    'Value': 'true'
                },
                {
                    'Name': 'name',
                    'Value': user_data["name"]
                },
                {
                    'Name': 'custom:role',
                    'Value': user_data["role"]
                }
            ]
        )
        
        # Extract Cognito user ID
        cognito_id = cognito_response['User']['Username']
        
        # Create user in database
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            cognito_id=cognito_id,
            email=user_data["email"],
            name=user_data["name"],
            role=user_data["role"],
            school_id=user_data.get("school_id")
        )
        db.add(user)
        
        # Add user to group in Cognito
        cognito_client.admin_add_user_to_group(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=user_data["email"],
            GroupName=user_data["role"] + "s"  # Pluralize the role for group name
        )
        
        # Log the user creation event
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            event_type="CREATE",
            resource_type="USER",
            resource_id=user_id,
            description=f"Created user {user_data['email']}",
            user_id=admin.id
        )
        db.add(audit_log)
        
        # Commit all database changes
        db.commit()
        
        return {
            "message": "User created successfully",
            "user_id": user_id,
            "cognito_id": cognito_id
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

# Utility functions
async def validate_csv_file(file_content: bytes, file_type: str, file_id: str):
    """
    Validate a CSV file to ensure it has the required format
    """
    try:
        # Get a new database session
        db = get_session()
        
        # Get file record
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            logger.error(f"File with ID {file_id} not found")
            return
        
        # Read CSV file with pandas
        df = pd.read_csv(pd.io.common.BytesIO(file_content))
        
        # Check for required columns based on file type
        required_columns = {
            "sections": ["section_id", "course_name", "capacity"],
            "students": ["student_id", "grade_level"],
            "teachers": ["teacher_id", "name"],
            "preferences": ["student_id", "section_id", "preference_rank"]
        }
        
        validation_errors = []
        if file_type in required_columns:
            missing_columns = [col for col in required_columns[file_type] if col not in df.columns]
            if missing_columns:
                validation_errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        
        # Update file record with validation results
        if validation_errors:
            file.validation_status = "INVALID"
            file.validation_errors = validation_errors
            logger.warning(f"Validation errors for {file_type} file: {validation_errors}")
        else:
            file.validation_status = "VALID"
            file.metadata = {
                "columns": df.columns.tolist(),
                "row_count": len(df),
                "file_type": file_type
            }
            logger.info(f"Successfully validated {file_type} file")
        
        # Commit changes
        db.commit()
        
    except Exception as e:
        logger.error(f"Error validating {file_type} file: {str(e)}")
        
        # Try to update file record with error
        try:
            db = get_session()
            file = db.query(File).filter(File.id == file_id).first()
            if file:
                file.validation_status = "INVALID"
                file.validation_errors = [f"Error during validation: {str(e)}"]
                db.commit()
        except Exception as inner_e:
            logger.error(f"Error updating file validation status: {str(inner_e)}")
    finally:
        try:
            db.close()
        except:
            pass

# Create Lambda handler
handler = Mangum(app)