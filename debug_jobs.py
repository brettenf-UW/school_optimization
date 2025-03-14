#!/usr/bin/env python
import boto3
import argparse
import json
from tabulate import tabulate
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

# Database connection details
DB_HOST = os.environ.get('DB_HOST', 'localhost')  
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'postgres')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')

def get_db_connection():
    """Get a connection to the database"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return None

def list_jobs(limit=20, status=None, school_id=None):
    """List jobs from the database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = "SELECT id, name, job_type, status, progress, error_message, created_at, started_at, completed_at, school_id, user_id FROM job"
            params = []
            
            where_clauses = []
            if status:
                where_clauses.append("status = %s")
                params.append(status)
            
            if school_id:
                where_clauses.append("school_id = %s")
                params.append(school_id)
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            jobs = cursor.fetchall()
            
            # Format dates for display
            for job in jobs:
                for date_field in ['created_at', 'started_at', 'completed_at']:
                    if job[date_field]:
                        job[date_field] = job[date_field].strftime('%Y-%m-%d %H:%M:%S')
            
            # Print table of jobs
            print(tabulate(jobs, headers="keys", tablefmt="grid"))
            
            return jobs
    except Exception as e:
        print(f"Error listing jobs: {str(e)}")
        return []
    finally:
        conn.close()

def get_job_details(job_id):
    """Get detailed information about a specific job"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get job information
            cursor.execute(
                "SELECT * FROM job WHERE id = %s",
                (job_id,)
            )
            job = cursor.fetchone()
            
            if not job:
                print(f"Job with ID {job_id} not found")
                return None
            
            # Format job data for display
            for key, value in job.items():
                if isinstance(value, datetime):
                    job[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                elif key == 'parameters' or key == 'result_summary':
                    if value:
                        job[key] = json.dumps(value, indent=2)
            
            # Get associated files
            cursor.execute(
                "SELECT id, name, file_type, validation_status, is_input, created_at FROM file WHERE job_id = %s",
                (job_id,)
            )
            files = cursor.fetchall()
            
            # Format file dates
            for file in files:
                if file['created_at']:
                    file['created_at'] = file['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Display job details
            print("JOB DETAILS:")
            print("-" * 50)
            for key, value in job.items():
                print(f"{key}: {value}")
            
            # Display associated files
            if files:
                print("\nASSOCIATED FILES:")
                print("-" * 50)
                print(tabulate(files, headers="keys", tablefmt="grid"))
            
            return {
                'job': job,
                'files': files
            }
    except Exception as e:
        print(f"Error getting job details: {str(e)}")
        return None
    finally:
        conn.close()

def check_batch_job(job_id):
    """Check AWS Batch status for a job"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        # First get the Batch job ID from the database
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT parameters FROM job WHERE id = %s",
                (job_id,)
            )
            job = cursor.fetchone()
            
            if not job or not job['parameters'] or 'batch_job_id' not in job['parameters']:
                print(f"No AWS Batch job ID found for job {job_id}")
                return None
            
            batch_job_id = job['parameters'].get('batch_job_id')
            
            # Get AWS Batch job details
            batch = boto3.client('batch')
            response = batch.describe_jobs(jobs=[batch_job_id])
            
            if not response['jobs']:
                print(f"No Batch job found with ID {batch_job_id}")
                return None
            
            batch_job = response['jobs'][0]
            
            # Print key batch job details
            print("AWS BATCH JOB DETAILS:")
            print("-" * 60)
            print(f"Batch Job ID: {batch_job['jobId']}")
            print(f"Status: {batch_job['status']}")
            print(f"Status Reason: {batch_job.get('statusReason', 'N/A')}")
            print(f"Created At: {batch_job['createdAt']}")
            print(f"Started At: {batch_job.get('startedAt', 'N/A')}")
            print(f"Stopped At: {batch_job.get('stoppedAt', 'N/A')}")
            
            # Print container details if available
            if 'container' in batch_job:
                container = batch_job['container']
                print("\nCONTAINER DETAILS:")
                print("-" * 60)
                print(f"Exit Code: {container.get('exitCode', 'N/A')}")
                print(f"Reason: {container.get('reason', 'N/A')}")
                print(f"Log Stream: {container.get('logStreamName', 'N/A')}")
            
            return batch_job
    except Exception as e:
        print(f"Error checking batch job: {str(e)}")
        return None
    finally:
        conn.close()

def get_batch_logs(log_stream_name):
    """Get CloudWatch logs for a Batch job"""
    if not log_stream_name:
        print("No log stream name provided")
        return None
    
    try:
        logs = boto3.client('logs')
        response = logs.get_log_events(
            logGroupName='/aws/batch/job',  # Default log group for AWS Batch
            logStreamName=log_stream_name,
            limit=100
        )
        
        print("BATCH JOB LOGS:")
        print("-" * 80)
        
        for event in response['events']:
            timestamp = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] {event['message']}")
        
        return response['events']
    except Exception as e:
        print(f"Error getting batch logs: {str(e)}")
        return None

def retry_job(job_id):
    """Create a new job based on a failed job"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get the original job
            cursor.execute(
                "SELECT name, job_type, parameters, school_id, user_id, model_id FROM job WHERE id = %s",
                (job_id,)
            )
            original_job = cursor.fetchone()
            
            if not original_job:
                print(f"Job with ID {job_id} not found")
                return None
            
            # Get the associated files
            cursor.execute(
                "SELECT id FROM file WHERE job_id = %s AND is_input = TRUE",
                (job_id,)
            )
            files = cursor.fetchall()
            file_ids = [file['id'] for file in files]
            
            # Create a new job
            new_job_id = str(__import__('uuid').uuid4())
            new_job_name = f"Retry of {original_job['name']}"
            
            # Insert new job
            cursor.execute(
                """
                INSERT INTO job (id, name, job_type, status, parameters, user_id, school_id, model_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    new_job_id,
                    new_job_name,
                    original_job['job_type'],
                    'PENDING',
                    original_job['parameters'],
                    original_job['user_id'],
                    original_job['school_id'],
                    original_job['model_id']
                )
            )
            
            # Associate files with new job
            for file_id in file_ids:
                cursor.execute(
                    "UPDATE file SET job_id = %s WHERE id = %s",
                    (new_job_id, file_id)
                )
            
            # Create SQS message
            sqs = boto3.client('sqs')
            queue_url = os.environ.get('SQS_QUEUE_URL', 'https://sqs.us-west-2.amazonaws.com/your-account-id/echelon-jobs')
            
            sqs_message = {
                "job_id": new_job_id,
                "school_id": original_job['school_id'],
                "job_type": original_job['job_type'],
                "parameters": original_job['parameters'],
                "model_id": original_job['model_id'],
                "created_by": original_job['user_id']
            }
            
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(sqs_message),
                MessageAttributes={
                    'JobType': {
                        'DataType': 'String',
                        'StringValue': original_job['job_type']
                    },
                    'SchoolId': {
                        'DataType': 'String',
                        'StringValue': original_job['school_id']
                    }
                }
            )
            
            # Update job status
            cursor.execute(
                "UPDATE job SET status = 'QUEUED' WHERE id = %s",
                (new_job_id,)
            )
            
            conn.commit()
            
            print(f"Created new job {new_job_id} as retry of {job_id}")
            print(f"Job is now in QUEUED state")
            
            return new_job_id
    except Exception as e:
        conn.rollback()
        print(f"Error retrying job: {str(e)}")
        return None
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Debug jobs for school optimization')
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # List jobs command
    list_parser = subparsers.add_parser('list', help='List jobs')
    list_parser.add_argument('--limit', type=int, default=20, help='Max number of jobs to list')
    list_parser.add_argument('--status', help='Filter by status (e.g., FAILED, COMPLETED)')
    list_parser.add_argument('--school', help='Filter by school ID')
    
    # Get job details command
    get_parser = subparsers.add_parser('details', help='Get job details')
    get_parser.add_argument('--id', help='Job ID', required=True)
    
    # Check batch job command
    batch_parser = subparsers.add_parser('batch', help='Check AWS Batch job')
    batch_parser.add_argument('--id', help='Job ID', required=True)
    
    # Get batch logs command
    logs_parser = subparsers.add_parser('logs', help='Get AWS Batch logs')
    logs_parser.add_argument('--stream', help='Log stream name', required=True)
    
    # Retry job command
    retry_parser = subparsers.add_parser('retry', help='Retry a failed job')
    retry_parser.add_argument('--id', help='Job ID to retry', required=True)
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_jobs(args.limit, args.status, args.school)
    elif args.command == 'details':
        get_job_details(args.id)
    elif args.command == 'batch':
        check_batch_job(args.id)
    elif args.command == 'logs':
        get_batch_logs(args.stream)
    elif args.command == 'retry':
        retry_job(args.id)
    else:
        parser.print_help()
        sys.exit(1)