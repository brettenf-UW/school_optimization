# Echelon Scheduling Platform: Quick Start Guide

This guide provides a step-by-step approach to setting up the Echelon scheduling platform for Chico High School, emphasizing incremental development and testing.

## Overview

The Echelon scheduling system implements a complex educational timetabling solution that optimizes school schedules by combining:

1. Mathematical optimization (MILP) using Gurobi
2. AI-powered enhancement with Claude to improve utilization

The hybrid approach works iteratively:
- MILP creates an initial optimized schedule
- Claude analyzes and improves sections with low utilization (<75%)
- The modified schedule is fed back into MILP for further refinement
- This cycle continues until convergence or time limits are reached

## Incremental Development Plan

Rather than building everything at once, follow this incremental approach to make steady progress and identify issues early:

### Phase 1: Core Components Setup

#### Step 1: Create Basic AWS Infrastructure
```bash
# Create S3 bucket for file storage
aws s3 mb s3://echelon-chico-demo --region us-west-2

# Configure basic CORS policy
aws s3api put-bucket-cors --bucket echelon-chico-demo --cors-configuration file://simple-cors.json

# Create SQS queue for job processing
aws sqs create-queue --queue-name echelon-jobs-demo --region us-west-2
```

#### Step 2: Set Up Local Database
```bash
# Start PostgreSQL container
docker run --name echelon-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=echelon -d -p 5432:5432 postgres:13-alpine

# Verify database is running
docker ps | grep echelon-db
```

#### Step 3: Test File Upload to S3
```bash
# Upload test files to S3
aws s3 cp "Test Chico High CSVs/Sections_Information.csv" s3://echelon-chico-demo/test/sections/
aws s3 cp "Test Chico High CSVs/Student_Info.csv" s3://echelon-chico-demo/test/students/

# Verify files were uploaded
aws s3 ls s3://echelon-chico-demo/test/
```

#### Step 4: Test Database Schema
```bash
# Execute DB migration scripts
docker cp backend/db_migrations.py echelon-db:/tmp/
docker exec -it echelon-db python /tmp/db_migrations.py create

# Verify tables were created
docker exec -it echelon-db psql -U postgres -d echelon -c "\dt"
```

### Phase 2: Backend API Development

#### Step 1: Build and Test API Container
```bash
# Build API image
docker build -t echelon-api:test -f docker/Dockerfile.api .

# Run container with minimal configuration
docker run -d --name echelon-api-test -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/echelon \
  -e S3_BUCKET_NAME=echelon-chico-demo \
  -e ENVIRONMENT=development \
  echelon-api:test

# Test health endpoint
curl http://localhost:8000/api/health
```

#### Step 2: Test File Upload API
```bash
# Test file upload endpoint
curl -X POST \
  -F "school_id=chico-test" \
  -F "sections_file=@Test Chico High CSVs/Sections_Information.csv" \
  http://localhost:8000/api/upload/school-data

# Verify file was saved in S3
aws s3 ls s3://echelon-chico-demo/chico-test/
```

#### Step 3: Set Up Worker Service
```bash
# Build worker image
docker build -t echelon-worker:test -f docker/Dockerfile.worker .

# Run container with essential configuration
docker run -d --name echelon-worker-test \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/echelon \
  -e S3_BUCKET_NAME=echelon-chico-demo \
  -e SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name echelon-jobs-demo --query QueueUrl --output text) \
  -e ENVIRONMENT=development \
  echelon-worker:test

# Test worker connectivity
docker logs echelon-worker-test
```

### Phase 3: Optimizer Development

#### Step 1: Test Core MILP Algorithm
```bash
# Set up Python environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r backend/requirements.txt

# Run MILP solver directly with test data
mkdir -p test-results
python -c "
from core.milp_soft import ScheduleOptimizer
import pandas as pd
import os

# Create test directories
os.makedirs('test-data/input', exist_ok=True)
os.makedirs('test-data/output', exist_ok=True)

# Copy test files
test_files = {
    'sections': 'Test Chico High CSVs/Sections_Information.csv',
    'students': 'Test Chico High CSVs/Student_Info.csv',
    'teachers': 'Test Chico High CSVs/Teacher_Info.csv',
    'preferences': 'Test Chico High CSVs/Student_Preference_Info.csv',
    'periods': 'Test Chico High CSVs/Period.csv',
    'teacher_unavail': 'Test Chico High CSVs/Teacher_unavailability.csv'
}

for key, path in test_files.items():
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.to_csv(f'test-data/input/{os.path.basename(path)}', index=False)
        print(f'Processed {path}')

# Run optimizer with small dataset
optimizer = ScheduleOptimizer(use_s3=False)
optimizer.load_data('test-data/input')
optimizer.create_variables()
optimizer.add_constraints()
optimizer.set_objective()
optimizer.optimize(time_limit=60)  # 1 minute time limit for testing
optimizer.save_results('test-data/output')
print('Optimization test complete. Results in test-data/output/')
"
```

#### Step 2: Test Claude Integration
```bash
# Create directories for Claude
mkdir -p core/input core/output

# Copy test files
cp "Test Chico High CSVs"/*.csv core/input/

# Set API key for testing
export ANTHROPIC_API_KEY=your-api-key  # Replace with your actual key

# Test Claude optimizer in isolation
python core/utilization_optimizer.py

# Verify Claude output
cat core/output/optimization_results.json
```

#### Step 3: Create MILP-Claude Integration
```bash
# Create integration script
cat > core/hybrid_optimizer.py << 'EOF'
#!/usr/bin/env python3
"""
Hybrid optimization that combines MILP and Claude
"""
import os
import sys
import argparse
import json
import pandas as pd
from pathlib import Path

# Import optimizers
from milp_soft import ScheduleOptimizer as MILPOptimizer
from utilization_optimizer import UtilizationOptimizer

class HybridOptimizer:
    def __init__(self, input_dir, output_dir, use_s3=False, api_key=None, bucket_name=None):
        """Initialize hybrid optimizer with both MILP and Claude"""
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.use_s3 = use_s3
        self.bucket_name = bucket_name
        self.iteration = 0
        self.max_iterations = 3
        self.improvement_threshold = 0.02  # 2% improvement threshold
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize MILP optimizer
        self.milp = MILPOptimizer(use_s3=use_s3, bucket_name=bucket_name)
        
        # Initialize Claude optimizer if API key provided
        self.claude = None
        if api_key:
            self.claude = UtilizationOptimizer(api_key)
    
    def optimize(self, time_limit=600):
        """Run iterative optimization process"""
        print(f"Starting hybrid optimization with max {self.max_iterations} iterations")
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        
        # 1. Initial MILP optimization
        print("\n--- Iteration 1: Initial MILP Optimization ---")
        self.milp.load_data(self.input_dir)
        self.milp.create_variables()
        self.milp.add_constraints()
        self.milp.set_objective()
        initial_obj = self.milp.optimize(time_limit=time_limit)
        self.milp.save_results(self.output_dir)
        
        # If Claude not available, stop after MILP
        if not self.claude:
            print("Claude API key not provided. Stopping after MILP optimization.")
            return initial_obj
        
        # 2. Iterative refinement
        prev_obj = initial_obj
        for i in range(2, self.max_iterations + 1):
            # Run Claude to improve utilization
            print(f"\n--- Iteration {i}a: Claude Utilization Improvement ---")
            self.claude.input_path = self.input_dir
            self.claude.output_path = self.output_dir
            self.claude.optimize()
            
            # Run MILP with Claude's improved schedule
            print(f"\n--- Iteration {i}b: MILP Refinement ---")
            self.milp.load_data(self.input_dir)  # Reload with Claude's changes
            self.milp.create_variables()
            self.milp.add_constraints()
            self.milp.set_objective()
            new_obj = self.milp.optimize(time_limit=time_limit)
            self.milp.save_results(self.output_dir)
            
            # Check for convergence
            improvement = (new_obj - prev_obj) / abs(prev_obj) if prev_obj != 0 else 0
            print(f"Iteration {i} improvement: {improvement:.4f}")
            
            if abs(improvement) < self.improvement_threshold:
                print(f"Converged after {i} iterations (improvement below threshold)")
                break
                
            prev_obj = new_obj
            
        print("\nHybrid optimization complete")
        return prev_obj

def main():
    parser = argparse.ArgumentParser(description='Run hybrid MILP-Claude optimization')
    parser.add_argument('--input', required=True, help='Input directory')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--time-limit', type=int, default=600, help='Time limit per iteration in seconds')
    parser.add_argument('--s3', action='store_true', help='Use S3 storage')
    parser.add_argument('--bucket', help='S3 bucket name')
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not found in environment. Claude optimization will be skipped.")
    
    # Run optimization
    optimizer = HybridOptimizer(
        input_dir=args.input,
        output_dir=args.output,
        use_s3=args.s3,
        api_key=api_key,
        bucket_name=args.bucket
    )
    
    result = optimizer.optimize(time_limit=args.time_limit)
    print(f"Final optimization result: {result}")

if __name__ == "__main__":
    main()
EOF

# Test integration script
python core/hybrid_optimizer.py --input core/input --output core/output --time-limit 60
```

#### Step 4: Set Up AWS Batch for Optimizer
```bash
# Create IAM role for Batch
aws iam create-role --role-name EchelonBatchDemo --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"batch.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

# Attach necessary policies
aws iam attach-role-policy --role-name EchelonBatchDemo --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam attach-role-policy --role-name EchelonBatchDemo --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam attach-role-policy --role-name EchelonBatchDemo --policy-arn arn:aws:iam::aws:policy/AmazonSQSFullAccess

# Get default VPC information
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[*].SubnetId" --output text | tr '\t' ',')
SECURITY_GROUP_ID=$(aws ec2 create-security-group --group-name EchelonBatchDemo --description "Echelon Batch Demo" --vpc-id $VPC_ID --query "GroupId" --output text)

# Create compute environment with minimal resources for testing
aws batch create-compute-environment \
  --compute-environment-name echelon-demo-compute-env \
  --type MANAGED \
  --state ENABLED \
  --compute-resources type=EC2,minvCpus=0,maxvCpus=4,desiredvCpus=0,instanceTypes=c5.xlarge,subnets=$SUBNET_IDS,securityGroupIds=$SECURITY_GROUP_ID \
  --service-role EchelonBatchDemo

# Create job queue
aws batch create-job-queue \
  --job-queue-name echelon-demo-job-queue \
  --state ENABLED \
  --priority 1 \
  --compute-environment-order order=1,computeEnvironment=echelon-demo-compute-env

# Build and push Docker image
aws ecr create-repository --repository-name echelon-optimization-demo --region us-west-2
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-west-2.amazonaws.com
docker build -t $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-west-2.amazonaws.com/echelon-optimization-demo:latest -f docker/Dockerfile.optimizer .
docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-west-2.amazonaws.com/echelon-optimization-demo:latest

# Register job definition with hybrid optimizer
aws batch register-job-definition \
  --job-definition-name echelon-optimization-demo \
  --type container \
  --container-properties '{"image":"'$(aws sts get-caller-identity --query Account --output text)'.dkr.ecr.us-west-2.amazonaws.com/echelon-optimization-demo:latest","vcpus":2,"memory":4096,"command":["python","/app/core/hybrid_optimizer.py","--input","/data/input","--output","/data/output","--s3","--bucket","echelon-chico-demo"],"environment":[{"name":"S3_BUCKET_NAME","value":"echelon-chico-demo"},{"name":"SQS_QUEUE_URL","value":"'$(aws sqs get-queue-url --queue-name echelon-jobs-demo --query QueueUrl --output text)'"},{"name":"ENVIRONMENT","value":"demo"}]}'
```

### Phase 4: End-to-End Integration

#### Step 1: Deploy All Services Together
```bash
# Start all services using docker-compose
cat > docker-compose.test.yml << 'EOF'
version: '3'
services:
  db:
    image: postgres:13-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: echelon
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    depends_on:
      - db
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/echelon
      - S3_BUCKET_NAME=echelon-chico-demo
      - SQS_QUEUE_URL=${SQS_QUEUE_URL:-http://localhost:9324/queue/echelon-jobs-demo}
      - BATCH_JOB_QUEUE=echelon-demo-job-queue
      - BATCH_JOB_DEFINITION=echelon-optimization-demo
      - ENVIRONMENT=development

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/echelon
      - S3_BUCKET_NAME=echelon-chico-demo
      - SQS_QUEUE_URL=${SQS_QUEUE_URL:-http://localhost:9324/queue/echelon-jobs-demo}
      - BATCH_JOB_QUEUE=echelon-demo-job-queue
      - BATCH_JOB_DEFINITION=echelon-optimization-demo
      - ENVIRONMENT=development

  frontend:
    build:
      context: ./frontend
      dockerfile: ../docker/Dockerfile.frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_USE_MOCK_AUTH=true

volumes:
  postgres_data:
EOF

# Set SQS queue URL environment variable
export SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name echelon-jobs-demo --query QueueUrl --output text)

# Start services
docker-compose -f docker-compose.test.yml up -d

# Initialize database
docker-compose -f docker-compose.test.yml exec api python backend/db_migrations.py create
docker-compose -f docker-compose.test.yml exec api python backend/db_migrations.py seed

# Create Chico High School record
docker-compose -f docker-compose.test.yml exec api python -c "
from backend.models import get_session, School
import uuid
db = get_session()
school = School(
    id='chico-high',
    name='Chico High School',
    district='Chico Unified School District',
    address='901 Esplanade, Chico, CA 95926',
    contact_email='info@chicohigh.org',
    phone='530-891-3026',
    student_count=1800,
    grade_levels='9-12'
)
db.add(school)
db.commit()
print('Chico High School record created')
"
```

#### Step 2: Test End-to-End Flow with Small Dataset
```bash
# Upload test files to S3 for Chico High
aws s3 cp "Test Chico High CSVs/Sections_Information.csv" s3://echelon-chico-demo/chico-high/sections/
aws s3 cp "Test Chico High CSVs/Student_Info.csv" s3://echelon-chico-demo/chico-high/students/
aws s3 cp "Test Chico High CSVs/Teacher_Info.csv" s3://echelon-chico-demo/chico-high/teachers/
aws s3 cp "Test Chico High CSVs/Student_Preference_Info.csv" s3://echelon-chico-demo/chico-high/preferences/
aws s3 cp "Test Chico High CSVs/Teacher_unavailability.csv" s3://echelon-chico-demo/chico-high/teachers/
aws s3 cp "Test Chico High CSVs/Period.csv" s3://echelon-chico-demo/chico-high/sections/

# Register files in database
docker-compose -f docker-compose.test.yml exec api python -c "
from backend.models import get_session, File, School
import uuid
import boto3

# Connect to S3
s3_client = boto3.client('s3')
s3_bucket = 'echelon-chico-demo'

# Connect to database
db = get_session()
school = db.query(School).filter(School.id == 'chico-high').first()

# Map of file types to S3 keys
file_mappings = [
    {'type': 'sections', 'key': 'chico-high/sections/Sections_Information.csv', 'name': 'Sections_Information.csv'},
    {'type': 'students', 'key': 'chico-high/students/Student_Info.csv', 'name': 'Student_Info.csv'},
    {'type': 'teachers', 'key': 'chico-high/teachers/Teacher_Info.csv', 'name': 'Teacher_Info.csv'},
    {'type': 'preferences', 'key': 'chico-high/preferences/Student_Preference_Info.csv', 'name': 'Student_Preference_Info.csv'},
    {'type': 'teachers', 'key': 'chico-high/teachers/Teacher_unavailability.csv', 'name': 'Teacher_unavailability.csv'},
    {'type': 'sections', 'key': 'chico-high/sections/Period.csv', 'name': 'Period.csv'}
]

# Register each file
for file_info in file_mappings:
    # Get file metadata from S3
    response = s3_client.head_object(Bucket=s3_bucket, Key=file_info['key'])
    file_size = response['ContentLength']
    
    # Create database record
    db_file = File(
        id=str(uuid.uuid4()),
        name=file_info['name'],
        file_type=file_info['type'],
        s3_key=file_info['key'],
        content_type='text/csv',
        size=file_size,
        is_input=True,
        validation_status='VALID',
        school_id=school.id
    )
    db.add(db_file)
    print(f'Registered {file_info[\"name\"]}')

db.commit()
print('All files registered successfully')
"

# Create test optimization job using reduced parameters
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "schedule_optimization",
    "name": "Chico High Test",
    "school_id": "chico-high",
    "parameters": {
      "optimization_type": "hybrid",
      "time_limit": 60,
      "max_iterations": 2
    }
  }' \
  http://localhost:8000/api/jobs/schedule

# Monitor job status
docker-compose -f docker-compose.test.yml logs -f worker
```

#### Step 3: Test Results Viewing
```bash
# Check job status in database
docker-compose -f docker-compose.test.yml exec api python -c "
from backend.models import get_session, Job
db = get_session()
job = db.query(Job).order_by(Job.created_at.desc()).first()
print(f'Job ID: {job.id}')
print(f'Status: {job.status}')
if job.batch_job_id:
    print(f'Batch Job ID: {job.batch_job_id}')
"

# Check AWS Batch job status
JOB_ID=$(docker-compose -f docker-compose.test.yml exec api python -c "
from backend.models import get_session, Job
db = get_session()
job = db.query(Job).order_by(Job.created_at.desc()).first()
print(job.batch_job_id)
" | tr -d '\r')

aws batch describe-jobs --jobs $JOB_ID

# Download results when job completes
ECHELON_JOB_ID=$(docker-compose -f docker-compose.test.yml exec api python -c "
from backend.models import get_session, Job
db = get_session()
job = db.query(Job).order_by(Job.created_at.desc()).first()
print(job.id)
" | tr -d '\r')

mkdir -p results
aws s3 cp s3://echelon-chico-demo/job-results/$ECHELON_JOB_ID/ ./results/ --recursive

# Create viewer for the results
cat > results/viewer.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Echelon Schedule Viewer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .container { display: flex; }
        .menu { width: 200px; margin-right: 20px; }
        .content { flex-grow: 1; }
        button { margin-bottom: 10px; width: 100%; padding: 8px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>Echelon Schedule Viewer</h1>
    <div class="container">
        <div class="menu">
            <h3>View Options</h3>
            <button onclick="loadCSV('student_schedule.csv')">Student Schedule</button>
            <button onclick="loadCSV('teacher_schedule.csv')">Teacher Schedule</button>
            <button onclick="loadCSV('section_schedule.csv')">Section Schedule</button>
        </div>
        <div class="content">
            <div id="tableContainer"></div>
        </div>
    </div>

    <script>
        function loadCSV(filename) {
            fetch(filename)
                .then(response => response.text())
                .then(data => {
                    const rows = data.trim().split('\n');
                    const headers = rows[0].split(',');
                    
                    let tableHTML = '<table><tr>';
                    headers.forEach(header => {
                        tableHTML += `<th>${header}</th>`;
                    });
                    tableHTML += '</tr>';
                    
                    for (let i = 1; i < rows.length; i++) {
                        const columns = rows[i].split(',');
                        tableHTML += '<tr>';
                        columns.forEach(column => {
                            tableHTML += `<td>${column}</td>`;
                        });
                        tableHTML += '</tr>';
                    }
                    
                    tableHTML += '</table>';
                    document.getElementById('tableContainer').innerHTML = tableHTML;
                })
                .catch(error => {
                    console.error('Error loading CSV:', error);
                    document.getElementById('tableContainer').innerHTML = 
                        `<p>Error loading file. Make sure ${filename} exists in the same directory.</p>`;
                });
        }
        
        // Load student schedule by default
        document.addEventListener('DOMContentLoaded', () => {
            loadCSV('student_schedule.csv');
        });
    </script>
</body>
</html>
EOF

# Serve the results
cd results
python -m http.server 8888
```

### Phase 5: Scale Up and Deploy Full Version

#### Step 1: Scale Up AWS Batch Resources
```bash
# Update compute environment with larger instance types
aws batch update-compute-environment \
  --compute-environment echelon-demo-compute-env \
  --compute-resources minvCpus=0,maxvCpus=16,desiredvCpus=0,instanceTypes=c5.4xlarge,r5.4xlarge

# Update job definition with more resources
aws batch register-job-definition \
  --job-definition-name echelon-optimization-demo \
  --type container \
  --container-properties '{"image":"'$(aws sts get-caller-identity --query Account --output text)'.dkr.ecr.us-west-2.amazonaws.com/echelon-optimization-demo:latest","vcpus":4,"memory":16384,"command":["python","/app/core/hybrid_optimizer.py","--input","/data/input","--output","/data/output","--s3","--bucket","echelon-chico-demo","--time-limit","1800"],"environment":[{"name":"S3_BUCKET_NAME","value":"echelon-chico-demo"},{"name":"SQS_QUEUE_URL","value":"'$(aws sqs get-queue-url --queue-name echelon-jobs-demo --query QueueUrl --output text)'"},{"name":"ENVIRONMENT","value":"demo"}]}'
```

#### Step 2: Test Full Dataset
```bash
# Create job with larger time limit
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "schedule_optimization",
    "name": "Chico High Full Run",
    "school_id": "chico-high",
    "parameters": {
      "optimization_type": "hybrid",
      "time_limit": 1800,
      "max_iterations": 3
    }
  }' \
  http://localhost:8000/api/jobs/schedule
```

#### Step 3: Set Up Frontend for Production
```bash
# Build frontend for production
cd frontend
npm install
npm run build

# Serve production build
docker run -d -p 80:80 -v $(pwd)/dist:/usr/share/nginx/html nginx:alpine
```

## Understanding the MILP-Claude Integration

The hybrid optimization approach combines the strengths of both MILP and Claude:

1. **MILP (Mixed Integer Linear Programming)**:
   - Creates mathematically optimal schedules
   - Handles hard constraints (teacher availability, period restrictions)
   - Ensures basic schedule validity

2. **Claude AI Enhancement**:
   - Analyzes utilization patterns across sections
   - Identifies under-utilized sections (<75% capacity)
   - Makes targeted improvements:
     - Merging low-enrollment sections
     - Splitting overfilled sections
     - Reallocating teachers to balance loads
     - Optimizing SPED student distribution

3. **Iterative Refinement Process**:
   ```
   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
   │                 │     │                 │     │                 │
   │  Initial Data   │────>│  MILP Solver    │────>│ Claude Analysis │
   │                 │     │                 │     │                 │
   └─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                            │
                                                            │
   ┌─────────────────┐     ┌─────────────────┐     ┌────────▼────────┐
   │                 │     │                 │     │                 │
   │  Final Schedule │<────│  MILP Solver    │<────│   Adjustments   │
   │                 │     │                 │     │                 │
   └─────────────────┘     └─────────────────┘     └─────────────────┘
   ```

The key integration points are:
1. MILP creates an initial schedule
2. Claude analyzes section utilization, focusing on any under 75% full
3. Claude makes targeted adjustments to improve utilization 
4. The adjusted schedule is fed back into MILP
5. MILP re-optimizes with the new structure
6. This cycle continues until either:
   - Utilization targets are met
   - No further improvements are possible
   - Maximum iterations are reached
   - Time limit is exceeded

## Critical Constraints for Chico High School

### Course-Specific Requirements

1. **Medical Career**:
   - Must be scheduled ONLY in R1 or G1 periods
   - Must have exactly one dedicated teacher who teaches NO other courses
   - Each section must have 15 seats maximum
   - Teacher cannot teach Heroes Teach

2. **Heroes Teach**:
   - Must be scheduled ONLY in R2 or G2 periods
   - Must have exactly one dedicated teacher who teaches NO other courses
   - Each section must have 15 seats maximum
   - Teacher cannot teach Medical Career

3. **Sports Med**:
   - Maximum 1 section per period
   - Standard class size rules apply
   - Can be scheduled in any period

### General Constraints

1. **Special Education**:
   - Maximum 3 SPED students per section
   - SPED students need to be distributed evenly

2. **Section Sizes**:
   - Minimum: 10 students
   - Maximum: 40 students
   - Target utilization: ≥75%

3. **Teacher Loads**:
   - Maximum 6 sections per teacher
   - Teachers must teach within their department

4. **Period Structure**:
   - 8 periods total: R1-R4, G1-G4
   - Specific courses have period restrictions

## Troubleshooting Guide

### AWS Infrastructure Issues

#### S3 Bucket
```bash
# Check bucket exists
aws s3 ls s3://echelon-chico-demo/

# Test bucket permissions
aws s3 cp test.txt s3://echelon-chico-demo/test.txt
aws s3 rm s3://echelon-chico-demo/test.txt
```

#### SQS Queue
```bash
# Check queue attributes
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name echelon-jobs-demo --query QueueUrl --output text) \
  --attribute-names All

# Send test message
aws sqs send-message \
  --queue-url $(aws sqs get-queue-url --queue-name echelon-jobs-demo --query QueueUrl --output text) \
  --message-body '{"test": "message"}'
```

#### AWS Batch
```bash
# Check compute environment status
aws batch describe-compute-environments --compute-environments echelon-demo-compute-env

# Check job queue status
aws batch describe-job-queues --job-queues echelon-demo-job-queue

# Check recent jobs
aws batch list-jobs --job-queue echelon-demo-job-queue --status RUNNING
aws batch list-jobs --job-queue echelon-demo-job-queue --status FAILED
```

### Container and Database Issues

```bash
# Check container logs
docker-compose -f docker-compose.test.yml logs api
docker-compose -f docker-compose.test.yml logs worker

# Check database
docker-compose -f docker-compose.test.yml exec db psql -U postgres -d echelon -c "SELECT * FROM job ORDER BY created_at DESC LIMIT 5;"

# Restart services
docker-compose -f docker-compose.test.yml restart api worker
```

### Optimizer Issues

```bash
# Test MILP directly
python -c "
from core.milp_soft import ScheduleOptimizer
optimizer = ScheduleOptimizer(use_s3=False)
optimizer.load_data('core/input')
optimizer.create_variables()
optimizer.add_constraints()
optimizer.set_objective()
optimizer.optimize(time_limit=60)
optimizer.save_results('core/output')
print('Test complete')
"

# Check if Gurobi is working
python -c "
import gurobipy as gp
try:
    m = gp.Model()
    x = m.addVar(name='x')
    m.setObjective(x, gp.GRB.MAXIMIZE)
    m.addConstr(x <= 10)
    m.optimize()
    print(f'Optimization status: {m.status}, value: {m.objVal}')
except Exception as e:
    print(f'Error: {e}')
"

# Test Claude API
python -c "
import anthropic
import os

api_key = os.environ.get('ANTHROPIC_API_KEY')
if not api_key:
    print('ANTHROPIC_API_KEY not set')
    exit(1)

client = anthropic.Anthropic(api_key=api_key)
message = client.messages.create(
    model='claude-3-haiku-20240307',
    max_tokens=100,
    messages=[{'role': 'user', 'content': 'Say hello'}]
)
print(message.content[0].text)
"
```

This comprehensive guide provides a modular, step-by-step approach to building the Echelon platform. By breaking down the development into phases and testing each component individually, you'll be able to make steady progress and identify issues early.