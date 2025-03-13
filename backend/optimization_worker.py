#!/usr/bin/env python3
"""
Optimization Worker Process

This script listens to the SQS queue for optimization job requests,
processes them by launching AWS Batch jobs, and updates job status in the database.

The worker runs as a long-lived process, either in a container or on an EC2 instance.
"""

import os
import json
import time
import logging
import boto3
import traceback
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize AWS clients
sqs_client = boto3.client('sqs')
batch_client = boto3.client('batch')
s3_client = boto3.client('s3')

# Get environment variables
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'echelon-data')
BATCH_JOB_QUEUE = os.environ.get('BATCH_JOB_QUEUE')
BATCH_JOB_DEFINITION = os.environ.get('BATCH_JOB_DEFINITION')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# Setup database connection (using SQLAlchemy)
from models import get_session, Job, File
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def process_job_request(message_body):
    """Process a job request from SQS."""
    db = get_session()
    
    try:
        # Parse message body
        job_request = json.loads(message_body)
        job_id = job_request.get('job_id')
        school_id = job_request.get('school_id')
        job_type = job_request.get('job_type')
        parameters = job_request.get('parameters', {})
        
        logger.info(f"Processing job request: {job_id} for school {school_id}, type {job_type}")
        
        # Get job from database
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found in database")
            return False
        
        # Update job status to PROCESSING
        job.status = "PROCESSING"
        job.started_at = datetime.now()
        db.commit()
        
        # Determine optimization type
        optimization_type = parameters.get('optimization_type', 'milp_soft')
        
        # Submit job to AWS Batch
        submit_batch_job(job_id, school_id, optimization_type)
        
        # Update job status to RUNNING
        job.status = "RUNNING"
        job.progress = 0
        db.commit()
        
        logger.info(f"Job {job_id} submitted to AWS Batch successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error processing job request: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update job status to FAILED
        try:
            if job:
                job.status = "FAILED"
                job.error_message = f"Error submitting to AWS Batch: {str(e)}"
                db.commit()
        except Exception as db_error:
            logger.error(f"Error updating job status: {str(db_error)}")
        
        return False
    finally:
        db.close()

def submit_batch_job(job_id, school_id, optimization_type='milp_soft'):
    """Submit a job to AWS Batch."""
    try:
        # Validate BATCH_JOB_QUEUE and BATCH_JOB_DEFINITION
        if not BATCH_JOB_QUEUE or not BATCH_JOB_DEFINITION:
            raise ValueError("Missing AWS Batch configuration: BATCH_JOB_QUEUE or BATCH_JOB_DEFINITION")
        
        # Prepare job parameters
        job_name = f"{ENVIRONMENT}-{school_id}-{optimization_type}-{job_id[:8]}"
        
        # Prepare environment variables for the job
        environment = [
            {"name": "USE_S3", "value": "true"},
            {"name": "BUCKET_NAME", "value": S3_BUCKET_NAME},
            {"name": "SCHOOL_ID", "value": school_id},
            {"name": "SCHOOL_PREFIX", "value": "input-data"},
            {"name": "OPTIMIZATION_TYPE", "value": optimization_type},
            {"name": "JOB_ID", "value": job_id}
        ]
        
        # Submit the job to AWS Batch
        response = batch_client.submit_job(
            jobName=job_name,
            jobQueue=BATCH_JOB_QUEUE,
            jobDefinition=BATCH_JOB_DEFINITION,
            containerOverrides={
                "environment": environment
            }
        )
        
        batch_job_id = response['jobId']
        logger.info(f"AWS Batch job submitted: {batch_job_id} for Echelon job {job_id}")
        
        # Update job record with AWS Batch job ID
        db = get_session()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.batch_job_id = batch_job_id
            db.commit()
        db.close()
        
        return batch_job_id
        
    except Exception as e:
        logger.error(f"Error submitting batch job: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def poll_job_status():
    """Poll AWS Batch for job status updates and update database."""
    try:
        db = get_session()
        
        # Find jobs in RUNNING state with batch_job_id
        running_jobs = db.query(Job).filter(
            Job.status == "RUNNING",
            Job.batch_job_id.isnot(None)
        ).all()
        
        for job in running_jobs:
            try:
                # Get job status from AWS Batch
                response = batch_client.describe_jobs(jobs=[job.batch_job_id])
                
                if 'jobs' in response and len(response['jobs']) > 0:
                    batch_job = response['jobs'][0]
                    batch_status = batch_job['status']
                    
                    logger.info(f"Job {job.id} has AWS Batch status: {batch_status}")
                    
                    # Map AWS Batch status to our status
                    if batch_status == 'SUCCEEDED':
                        # Job completed successfully
                        job.status = "COMPLETED"
                        job.completed_at = datetime.now()
                        job.progress = 100
                        
                        # Calculate execution time
                        if job.started_at:
                            job.execution_time = (job.completed_at - job.started_at).total_seconds()
                        
                        # Get result details from S3
                        try:
                            s3_key = f"job-results/{job.id}/summary.json"
                            s3_obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                            result_data = json.loads(s3_obj['Body'].read().decode('utf-8'))
                            job.result_summary = result_data
                        except Exception as s3_error:
                            logger.error(f"Error getting result summary from S3: {str(s3_error)}")
                            
                    elif batch_status == 'FAILED':
                        # Job failed
                        job.status = "FAILED"
                        job.completed_at = datetime.now()
                        
                        # Get reason for failure
                        if 'statusReason' in batch_job:
                            job.error_message = batch_job['statusReason']
                            
                    elif batch_status == 'RUNNING':
                        # Job still running, update progress if available
                        if 'container' in batch_job and 'logStreamName' in batch_job['container']:
                            # Advanced feature: parse CloudWatch logs to estimate progress
                            # This would require additional setup with CloudWatch Logs
                            pass
                    
                    # Update database
                    db.commit()
                
            except Exception as job_error:
                logger.error(f"Error updating status for job {job.id}: {str(job_error)}")
                continue
        
    except Exception as e:
        logger.error(f"Error polling job status: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        if 'db' in locals():
            db.close()

def main():
    """Main entry point for the worker process."""
    if not SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL environment variable not set")
        return 1
        
    logger.info(f"Starting optimization worker, listening to SQS queue: {SQS_QUEUE_URL}")
    
    try:
        while True:
            try:
                # Poll SQS for messages
                response = sqs_client.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,  # Long polling
                    AttributeNames=['All'],
                    MessageAttributeNames=['All']
                )
                
                if 'Messages' in response:
                    for message in response['Messages']:
                        try:
                            # Process the message
                            receipt_handle = message['ReceiptHandle']
                            message_body = message['Body']
                            
                            logger.info(f"Received message: {message['MessageId']}")
                            
                            # Process the job request
                            if process_job_request(message_body):
                                # Delete message from queue if processed successfully
                                sqs_client.delete_message(
                                    QueueUrl=SQS_QUEUE_URL,
                                    ReceiptHandle=receipt_handle
                                )
                                logger.info(f"Deleted message {message['MessageId']} from queue")
                            else:
                                # Leave message in queue for retry
                                logger.info(f"Failed to process message {message['MessageId']}, will retry")
                                
                        except Exception as msg_error:
                            logger.error(f"Error processing message: {str(msg_error)}")
                            logger.error(traceback.format_exc())
                            continue
                
                # Check status of running batch jobs
                poll_job_status()
                
                # Sleep for a short time to prevent tight loop
                time.sleep(5)
                
            except Exception as loop_error:
                logger.error(f"Error in main loop: {str(loop_error)}")
                logger.error(traceback.format_exc())
                time.sleep(10)  # Sleep on error to prevent rapid retries
                
    except KeyboardInterrupt:
        logger.info("Worker process interrupted, shutting down")
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception in worker process: {str(e)}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())