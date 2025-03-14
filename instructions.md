# Echelon: Implementation Plan for Chico High School

This document provides a comprehensive implementation plan for deploying the Echelon scheduling optimization platform for Chico High School.

## Project Overview

Echelon is a cloud-based platform for optimizing school master schedules using advanced mathematical optimization techniques. It helps schools create optimal master schedules by:

- Maximizing student course satisfaction 
- Balancing teacher workloads
- Optimizing classroom utilization
- Handling complex scheduling constraints

## Architecture

Echelon uses a modern, cloud-based architecture with the following components:

1. **Frontend**: React TypeScript application with Material UI components
2. **Backend API**: FastAPI Python service for file processing and job management
3. **Worker Service**: Background process that manages the optimization job queue
4. **Database**: PostgreSQL for storing application data and job statuses
5. **AWS Services**:
   - **S3**: Stores input files and optimization results
   - **SQS**: Manages the job processing queue
   - **Batch**: Executes high-performance optimization jobs on scalable compute resources
   - **CloudWatch**: Monitors application performance and logs

## Implementation Plan

### 1. Local Development Environment Setup (Week 1)

1. **Setup Prerequisites**:
   - Install Docker and Docker Compose
   - Install AWS CLI and configure credentials
   - Install Gurobi for local testing (if you have a license)
   - Install Node.js 18+ and npm

2. **Database and Storage Preparation**:
   ```bash
   # Create local storage directories for development
   mkdir -p local-storage/chico-high-school/{sections,students,teachers,preferences}
   ```

3. **Configuration Updates**:
   - Edit the docker-compose.lite.yml to use local paths for testing
   ```yaml
   environment:
     - S3_BUCKET_NAME=local-echelon
     - SQS_QUEUE_URL=local-queue
     - ENVIRONMENT=development
   ```

4. **Deploy Local Services**:
   ```bash
   docker-compose -f docker-compose.lite.yml up --build
   ```

5. **Initialize Local Database**:
   ```bash
   docker-compose -f docker-compose.lite.yml exec api python db_migrations.py create
   docker-compose -f docker-compose.lite.yml exec api python db_migrations.py seed
   ```

### 2. Test Data Processing (Week 1-2)

1. **Format Validation**:
   - Copy the Test Chico High CSVs to local-storage directory
   - Run a test script to validate CSV formats:
   ```bash
   python check_data_quality.py --path "Test Chico High CSVs" --output validation_report.txt
   ```

2. **Data Ingestion Test**:
   - Use the API to upload test CSVs and verify they're processed correctly
   - Check the database for file records
   - Verify log files for proper processing messages

3. **Optimization Core Testing**:
   - Run the greedy.py algorithm directly with test data
   - Validate the initial solution for feasibility
   - Test the milp_soft.py optimizer with small data subset

### 3. AWS Infrastructure Setup (Week 2)

1. **Set Up Core AWS Resources**:
   ```bash
   # Run the provided setup script
   ./setup_resources.sh
   ```

2. **Configure S3 Bucket**:
   - Create a dedicated bucket for Chico High School:
   ```bash
   aws s3 mb s3://chico-high-scheduling --region us-west-2
   ```
   - Configure CORS policy for browser uploads:
   ```json
   {
     "CORSRules": [
       {
         "AllowedHeaders": ["*"],
         "AllowedMethods": ["GET", "PUT", "POST"],
         "AllowedOrigins": ["http://localhost:5173", "https://yourappdomainname.com"],
         "ExposeHeaders": ["ETag"]
       }
     ]
   }
   ```

3. **Set Up SQS Queue**:
   ```bash
   aws sqs create-queue --queue-name chico-high-optimization-queue --region us-west-2
   ```

4. **Configure AWS Batch**:
   - Deploy the CloudFormation template:
   ```bash
   aws cloudformation create-stack \
     --stack-name chico-high-batch \
     --template-body file://infrastructure/cloudformation/batch.yml \
     --parameters ParameterKey=EnvironmentName,ParameterValue=prod \
                 ParameterKey=MaxvCpus,ParameterValue=96 \
                 ParameterKey=DesiredvCpus,ParameterValue=0 \
     --capabilities CAPABILITY_IAM
   ```

5. **Build and Push Docker Images**:
   ```bash
   # Create ECR repository
   aws ecr create-repository --repository-name echelon-optimization
   
   # Build and push Docker image
   aws ecr get-login-password | docker login --username AWS --password-stdin {account-id}.dkr.ecr.{region}.amazonaws.com
   docker build -t {account-id}.dkr.ecr.{region}.amazonaws.com/echelon-optimization:latest -f docker/Dockerfile.optimizer .
   docker push {account-id}.dkr.ecr.{region}.amazonaws.com/echelon-optimization:latest
   ```

### 4. API Deployment (Week 3)

1. **Deploy Backend API**:
   - Use AWS Elastic Beanstalk or EC2 instance
   - Set environment variables:
   ```
   S3_BUCKET_NAME=chico-high-scheduling
   SQS_QUEUE_URL=https://sqs.us-west-2.amazonaws.com/{account-id}/chico-high-optimization-queue
   BATCH_JOB_QUEUE=prod-echelon-optimization-queue
   BATCH_JOB_DEFINITION=prod-echelon-optimization-job
   ENVIRONMENT=production
   ```

2. **Simplify Authentication**:
   - Modify the auth_api.py to use basic authentication or JWT without Cognito
   - Implement a simple user table in the database
   - Update the authentication middleware in app.py

3. **API Testing**:
   - Test health endpoint
   - Test file upload endpoints
   - Test job scheduling endpoints
   - Verify logs and database entries

### 5. Worker Implementation (Week 3)

1. **Deploy Worker Service**:
   - Use EC2 instance or ECS service
   - Set environment variables:
   ```
   S3_BUCKET_NAME=chico-high-scheduling
   SQS_QUEUE_URL=https://sqs.us-west-2.amazonaws.com/{account-id}/chico-high-optimization-queue
   BATCH_JOB_QUEUE=prod-echelon-optimization-queue
   BATCH_JOB_DEFINITION=prod-echelon-optimization-job
   ENVIRONMENT=production
   ```

2. **Worker Testing**:
   - Send test messages to SQS
   - Verify Batch job submissions
   - Monitor logs for proper processing

### 6. Frontend Deployment (Week 4)

1. **Configure Frontend**:
   - Update API endpoints in frontend/src/services/api.ts
   - Modify authentication logic to use basic auth or JWT

2. **Build Frontend**:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

3. **Deploy Frontend**:
   - Host on S3 with CloudFront, or
   - Host on EC2 instance with Nginx

### 7. End-to-End Testing (Week 4-5)

1. **Upload Test Data**:
   - Use the web interface to upload Chico High CSVs
   - Verify validation messages
   - Check database records

2. **Run Optimization Jobs**:
   - Schedule optimization through the web interface
   - Monitor job progress
   - Verify AWS Batch job execution

3. **Validate Results**:
   - Download and review generated schedules
   - Verify constraint compliance
   - Check for preference satisfaction
   - Validate teacher assignments

### 8. Performance Optimization (Week 5)

1. **Analyze Execution Times**:
   - Monitor AWS Batch execution metrics
   - Look for bottlenecks in processing

2. **Adjust Resource Allocation**:
   - Modify AWS Batch job definition if needed
   - Consider specialized instance types for faster execution

3. **Optimize Algorithms**:
   - Fine-tune MILP parameters for faster convergence
   - Improve greedy solution quality

### 9. Security Review (Week 6)

1. **IAM Permission Review**:
   ```bash
   ./check_aws_permissions.sh
   ```

2. **Data Encryption Verification**:
   - Verify S3 bucket encryption
   - Check database encryption
   - Validate SSL/TLS for all endpoints

3. **Authentication Testing**:
   - Test authentication flows
   - Verify token validation
   - Check authorization for protected resources

### 10. Deployment Planning for Production (Week 6-7)

1. **Documentation**:
   - Update all documentation with Chico-specific details
   - Create user guides for administrators
   - Document API endpoints

2. **Monitoring Setup**:
   - Configure CloudWatch alarms
   - Set up notification for job failures
   - Create dashboard for system health

3. **Backup Strategy**:
   - Database backup configuration
   - S3 versioning and lifecycle rules
   - Disaster recovery plan

### 11. User Training (Week 7)

1. **Admin Training Session**:
   - Walkthrough of data preparation
   - Demonstration of system usage
   - Review of output interpretation

2. **User Documentation**:
   - Create user guides
   - Record demo videos
   - Prepare FAQ document

### 12. Go-Live (Week 8)

1. **Final Data Upload**:
   - Upload final Chico High School data set
   - Verify data integrity
   - Get admin approval

2. **Production Optimization Run**:
   - Schedule full optimization job
   - Monitor execution closely
   - Validate final output

3. **Handover**:
   - Deliver documentation package
   - Provide admin credentials
   - Schedule follow-up support

## AWS Console Setup Instructions

### 1. S3 Console Setup

1. **Create Bucket**:
   - Navigate to S3 in AWS Console
   - Create a new bucket named "chico-high-scheduling"
   - Choose appropriate region (us-west-2 recommended)
   - Block all public access (security best practice)
   
2. **Configure Bucket Properties**:
   - Enable versioning
   - Enable server-side encryption with AWS managed keys
   
3. **Configure CORS**:
   - Go to Permissions tab
   - Edit CORS configuration
   - Add the following JSON:
   ```json
   [
     {
       "AllowedHeaders": ["*"],
       "AllowedMethods": ["GET", "PUT", "POST"],
       "AllowedOrigins": ["http://localhost:5173", "https://yourappdomainname.com"],
       "ExposeHeaders": ["ETag"]
     }
   ]
   ```

4. **Create Folder Structure**:
   - Create top-level folders:
     - `chico-high-school/`
     - `job-results/`
     - `uploads/`

### 2. IAM Console Setup

1. **Create Service Role**:
   - Navigate to IAM in AWS Console
   - Create a new role named "EchelonServiceRole"
   - Choose AWS service as trusted entity
   - Select EC2 as the use case
   
2. **Attach Policies**:
   - Attach these AWS managed policies:
     - AmazonS3FullAccess
     - AmazonSQSFullAccess
     - AmazonBatchFullAccess
     - CloudWatchLogsFullAccess
   
3. **Create Policy using provided template**:
   - Go to Policies
   - Create Policy
   - Use JSON editor
   - Paste contents from echelon-iam-policy.json
   - Name it "EchelonCustomPolicy"
   - Attach to EchelonServiceRole

### 3. SQS Console Setup

1. **Create Queue**:
   - Navigate to SQS in AWS Console
   - Create a new standard queue (not FIFO)
   - Name it "chico-high-optimization-queue"
   
2. **Configure Queue Properties**:
   - Set visibility timeout to 300 seconds (5 minutes)
   - Set message retention period to 14 days
   - Set maximum message size to 256 KB
   
3. **Configure Dead-Letter Queue**:
   - Create a new queue "chico-high-optimization-dlq"
   - Set message retention to 14 days
   - On the main queue, enable dead-letter queue
   - Select the DLQ you created
   - Set maximum receives to 5

### 4. AWS Batch Console Setup

1. **Create Compute Environment**:
   - Navigate to AWS Batch in the console
   - Create a compute environment
   - Choose "Managed" type
   - Name it "chico-high-compute-env"
   - Select "On-Demand" and "Spot" (create two separate environments for redundancy)
   
2. **Configure Compute Resources**:
   - Minimum vCPUs: 0
   - Maximum vCPUs: 96
   - Desired vCPUs: 0
   - Choose allowed instance types:
     - r6i.24xlarge (preferred for memory-intensive optimization)
     - c6i.24xlarge (as alternative)
   - Set Spot bid percentage to 70% (or adjust based on budget)
   
3. **Create Job Queue**:
   - Create a job queue named "chico-high-optimization-queue"
   - Set Priority to 1
   - Connect both compute environments:
     - Spot environment with order 1
     - On-demand environment with order 2
   
4. **Create Job Definition**:
   - Create a job definition named "chico-high-optimization-job"
   - Use the ECR image URL created earlier
   - Set vCPUs to 32
   - Set memory to 256GB
   - Add environment variables from the API deployment section
   - Set retry attempts to 2

## Component Testing Guide

### API Testing

```bash
# Health check
curl http://your-api-endpoint/api/health

# Upload test files (using browser or API tool like curl)
curl -X POST \
  -F "school_id=chico-high" \
  -F "sections_file=@Test Chico High CSVs/Sections_Information.csv" \
  -F "students_file=@Test Chico High CSVs/Student_Info.csv" \
  -F "teachers_file=@Test Chico High CSVs/Teacher_Info.csv" \
  -F "preferences_file=@Test Chico High CSVs/Student_Preference_Info.csv" \
  http://your-api-endpoint/api/upload/school-data
```

### Worker Testing

```bash
# Check worker logs
docker logs -f echelon-worker

# Monitor SQS queue
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-west-2.amazonaws.com/{account-id}/chico-high-optimization-queue \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

### Optimization Job Testing

```bash
# Submit test job
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"job_type": "schedule_optimization", "school_id": "chico-high", "parameters": {"optimization_type": "milp_soft"}}' \
  http://your-api-endpoint/api/jobs/schedule

# Check job status
curl http://your-api-endpoint/api/jobs/{job_id}
```

### AWS Batch Monitoring

```bash
# List jobs
aws batch list-jobs --job-queue chico-high-optimization-queue

# Describe job details
aws batch describe-jobs --jobs {job-id}
```

### Result Validation

```bash
# Download results
aws s3 cp s3://chico-high-scheduling/job-results/{job-id}/schedules/ ./results/ --recursive

# View sample results
head -n 10 ./results/student_schedule.csv
head -n 10 ./results/section_schedule.csv
head -n 10 ./results/teacher_schedule.csv
```

## Chico High School Specific Configuration

The system includes specific constraints for Chico High School:

1. **Period Structure**: Uses 8 periods in the schedule (R1-R4, G1-G4)
2. **Course Restrictions**:
   - Medical Career courses can only be scheduled in periods R1 or G1
   - Heroes Teach courses can only be scheduled in periods R2 or G2
3. **Special Education**: Distribution of SPED students is limited to maximum 12 per section
4. **Science Lab Scheduling**: Avoids scheduling science labs in consecutive periods

These constraints are implemented in the core/milp_soft.py file as follows:

```python
# Define course period restrictions
self.course_period_restrictions = {
    'Medical Career': ['R1', 'G1'],
    'Heroes Teach': ['R2', 'G2']
}
```

## File Format Requirements

### Sections_Information.csv
- Required columns:
  - `Section ID`: Unique identifier for each section
  - `Course ID`: Identifier for the course
  - `Teacher Assigned`: Teacher assigned to the section
  - `# of Seats Available`: Number of available seats in the section
  - `Department`: Department the section belongs to

### Student_Info.csv
- Required columns:
  - `Student ID`: Unique identifier for each student
  - `SPED`: Indicates special education status (Yes/No or 1/0)

### Teacher_Info.csv
- Required columns:
  - `Teacher ID`: Unique identifier for each teacher
  - `Department`: The department the teacher belongs to
  - `Dedicated Course`: Course the teacher is dedicated to teach
  - `Current Load`: Number of sections currently assigned
  - `Science Sections`: Number of science sections taught

### Student_Preference_Info.csv
- Required columns:
  - `Student ID`: Unique identifier for each student
  - `Preferred Sections`: Semicolon-separated list of course IDs (e.g., "Math101;Science202;History303")

### Teacher_unavailability.csv
- Required columns:
  - `Teacher ID`: Unique identifier for each teacher
  - `Unavailable Periods`: Semicolon-separated list of periods when the teacher is unavailable

### Period.csv
- Required columns:
  - `period_id`: Unique identifier for each period
  - `period_name`: Name of the period (R1-R4, G1-G4)