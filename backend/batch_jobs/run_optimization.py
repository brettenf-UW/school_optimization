#!/usr/bin/env python3
"""
AWS Batch Job Entry Point for School Schedule Optimization

This script serves as the entry point for AWS Batch jobs. It parses environment
variables, sets up logging, and runs the appropriate optimization algorithm for 
the specified school.

Environment variables:
    USE_S3: Set to "true" to use S3 storage (default: true)
    BUCKET_NAME: S3 bucket name (default: chico-high-school-optimization)
    SCHOOL_PREFIX: S3 prefix for school data (default: input-data)
    SCHOOL_ID: School identifier (default: chico-high-school)
    OPTIMIZATION_TYPE: Type of optimization to run (default: milp_soft)
"""

import os
import sys
import logging
import time
import json
from datetime import datetime
import boto3

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"/app/logs/optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

def get_env_var(name, default=None):
    """Get environment variable with default value."""
    value = os.environ.get(name, default)
    logger.info(f"Using {name}={value}")
    return value

def update_job_status(job_id, status, message, s3_bucket=None, results=None):
    """Update job status in S3 (or CloudWatch)."""
    status_update = {
        "job_id": job_id,
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "results": results or {}
    }
    
    # Log the status update
    logger.info(f"Job status update: {json.dumps(status_update)}")
    
    # If we have an S3 bucket, store the status there
    if s3_bucket:
        try:
            s3_client = boto3.client('s3')
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=f"job-status/{job_id}/status.json",
                Body=json.dumps(status_update),
                ContentType="application/json"
            )
        except Exception as e:
            logger.error(f"Failed to update job status in S3: {str(e)}")

def run_chico_high_milp():
    """Run the MILP optimization for Chico High School."""
    try:
        # Import here to isolate potential import errors
        sys.path.append('/app')
        
        logger.info("Importing optimization modules...")
        from backend.school_models.chico_high.milp_soft import ScheduleOptimizer
        
        # Get environment variables
        use_s3 = get_env_var('USE_S3', 'true').lower() == 'true'
        bucket_name = get_env_var('BUCKET_NAME', 'chico-high-school-optimization')
        school_prefix = get_env_var('SCHOOL_PREFIX', 'input-data')
        school_id = get_env_var('SCHOOL_ID', 'chico-high-school')
        job_id = get_env_var('AWS_BATCH_JOB_ID', f"local-{int(time.time())}")
        
        logger.info(f"Starting optimization job {job_id} for {school_id}...")
        update_job_status(job_id, "RUNNING", "Optimization started", bucket_name)
        
        # Initialize and run optimizer
        optimizer = ScheduleOptimizer(
            use_s3=use_s3,
            bucket_name=bucket_name,
            school_prefix=school_prefix,
            school_id=school_id
        )
        
        logger.info("Creating variables...")
        optimizer.create_variables()
        
        logger.info("Adding constraints...")
        optimizer.add_constraints()
        
        logger.info("Setting objective function...")
        optimizer.set_objective()
        
        logger.info("Solving optimization problem...")
        start_time = time.time()
        optimizer.solve()
        elapsed_time = time.time() - start_time
        
        # Check if solution was found
        if hasattr(optimizer.model, 'SolCount') and optimizer.model.SolCount > 0:
            # Get solution quality metrics
            missed_count = sum(var.X > 0.5 for var in optimizer.missed_request.values())
            total_requests = len(optimizer.missed_request)
            satisfied_requests = total_requests - missed_count
            satisfaction_rate = (satisfied_requests / total_requests) * 100
            
            message = f"Optimization completed successfully in {elapsed_time:.2f} seconds. "
            message += f"Satisfaction rate: {satisfaction_rate:.2f}%"
            
            # Store results
            results = {
                "status": "SUCCESS",
                "runtime_seconds": elapsed_time,
                "satisfaction_rate": satisfaction_rate,
                "satisfied_requests": int(satisfied_requests),
                "total_requests": total_requests
            }
            
            update_job_status(job_id, "COMPLETED", message, bucket_name, results)
            logger.info(f"Optimization job {job_id} completed successfully!")
            return 0
        else:
            message = f"Optimization completed but no solution found after {elapsed_time:.2f} seconds."
            update_job_status(job_id, "FAILED", message, bucket_name)
            logger.error(message)
            return 1
    
    except Exception as e:
        import traceback
        error_message = f"Error in optimization: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
        update_job_status(
            get_env_var('AWS_BATCH_JOB_ID', f"local-{int(time.time())}"),
            "FAILED", 
            f"Optimization failed: {str(e)}",
            get_env_var('BUCKET_NAME', 'chico-high-school-optimization')
        )
        return 1

def run_chico_high_greedy():
    """Run the greedy optimization for Chico High School."""
    try:
        # Import here to isolate potential import errors
        sys.path.append('/app')
        
        logger.info("Importing greedy optimization module...")
        from backend.school_models.common import greedy
        
        # Get environment variables
        use_s3 = get_env_var('USE_S3', 'true').lower() == 'true'
        bucket_name = get_env_var('BUCKET_NAME', 'chico-high-school-optimization')
        school_prefix = get_env_var('SCHOOL_PREFIX', 'input-data')
        school_id = get_env_var('SCHOOL_ID', 'chico-high-school')
        job_id = get_env_var('AWS_BATCH_JOB_ID', f"local-{int(time.time())}")
        
        logger.info(f"Starting greedy optimization job {job_id} for {school_id}...")
        update_job_status(job_id, "RUNNING", "Greedy optimization started", bucket_name)
        
        # Run the main function from greedy.py
        start_time = time.time()
        
        # Load data with S3 support
        students, student_preferences, teachers, sections, teacher_unavailability, periods = greedy.load_data(
            input_dir="/app/input",
            use_s3=use_s3,
            bucket_name=bucket_name,
            school_prefix=school_prefix,
            school_id=school_id
        )
        
        # Run greedy algorithm
        data = greedy.preprocess_data(students, student_preferences, teachers, sections, teacher_unavailability, periods)
        scheduled_sections = greedy.greedy_schedule_sections(sections, periods, data)
        student_assignments = greedy.greedy_assign_students(students, scheduled_sections, data)
        
        # Save results
        if use_s3 and bucket_name:
            greedy.save_solution_to_s3(student_assignments, scheduled_sections, sections, bucket_name, school_id)
        else:
            greedy.output_results(student_assignments, scheduled_sections, sections)
        
        # Calculate statistics
        section_count = len(scheduled_sections)
        total_sections = len(sections)
        total_assignments = sum(len(sections) for sections in student_assignments.values())
        total_requests = sum(len(courses) for courses in data['student_pref_courses'].values())
        
        elapsed_time = time.time() - start_time
        satisfaction_rate = (total_assignments / total_requests) * 100 if total_requests > 0 else 0
        
        message = f"Greedy optimization completed in {elapsed_time:.2f} seconds. "
        message += f"Satisfaction rate: {satisfaction_rate:.2f}%"
        
        # Store results
        results = {
            "status": "SUCCESS",
            "runtime_seconds": elapsed_time,
            "satisfaction_rate": satisfaction_rate,
            "satisfied_requests": total_assignments,
            "total_requests": total_requests,
            "scheduled_sections": section_count,
            "total_sections": total_sections
        }
        
        update_job_status(job_id, "COMPLETED", message, bucket_name, results)
        logger.info(f"Greedy optimization job {job_id} completed successfully!")
        return 0
    
    except Exception as e:
        import traceback
        error_message = f"Error in greedy optimization: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
        update_job_status(
            get_env_var('AWS_BATCH_JOB_ID', f"local-{int(time.time())}"),
            "FAILED", 
            f"Greedy optimization failed: {str(e)}",
            get_env_var('BUCKET_NAME', 'chico-high-school-optimization')
        )
        return 1

def main():
    """Main entry point."""
    try:
        # Get optimization type (defaults to milp_soft)
        optimization_type = get_env_var('OPTIMIZATION_TYPE', 'milp_soft')
        
        # Run the appropriate optimization based on type
        if optimization_type == 'milp_soft':
            logger.info("Running MILP optimization with soft constraints")
            return run_chico_high_milp()
        elif optimization_type == 'greedy':
            logger.info("Running greedy optimization")
            return run_chico_high_greedy()
        else:
            logger.error(f"Unknown optimization type: {optimization_type}")
            return 1
    
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())