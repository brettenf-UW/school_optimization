# Echelon: School Scheduling Optimization Platform

A cloud-based platform for optimizing school master schedules using advanced linear programming and mathematical optimization techniques.

## Project Overview

Echelon is designed to help schools create optimal master schedules by leveraging powerful cloud infrastructure and mathematical optimization. The platform:

- Provides a user-friendly web interface for uploading school data files
- Processes complex scheduling constraints using Gurobi's Mixed Integer Linear Programming solver
- Distributes computation across high-performance AWS Batch compute resources
- Delivers optimized schedules that maximize student course satisfaction
- Balances teacher workloads and classroom utilization
- Ensures security and compliance for sensitive school data
- Scales automatically to handle schools of any size

## Architecture

Echelon uses a modern, cloud-based architecture with the following components:

1. **Frontend**: React TypeScript application with Material UI components
2. **Backend API**: FastAPI Python service for file processing and job management
3. **Worker Service**: Background process that manages the optimization job queue
4. **Database**: PostgreSQL for storing application data, user information, and job statuses
5. **AWS Services**:
   - **S3**: Stores input files and optimization results
   - **SQS**: Manages the job processing queue
   - **Batch**: Executes high-performance optimization jobs on scalable compute resources
   - **Cognito**: Handles user authentication and authorization
   - **CloudWatch**: Monitors application performance and logs

## Directory Structure

```
Echelon/
├── core/                   # Core optimization algorithms
│   ├── load.py             # Data loading utilities
│   ├── greedy.py           # Greedy initial solution generator
│   └── milp_soft.py        # Mixed Integer Linear Programming solver
│
├── backend/                # API and backend services
│   ├── app.py              # Main API endpoints
│   ├── auth_api.py         # Authentication API
│   ├── models/             # Database models
│   │   ├── __init__.py     # Database connection
│   │   ├── user.py         # User model
│   │   ├── school.py       # School model
│   │   ├── job.py          # Job model
│   │   ├── file.py         # File model
│   ├── batch_jobs/         # AWS Batch job definitions
│   └── optimization_worker.py # SQS queue worker for job processing
│
├── frontend/              # React frontend application
│   ├── src/               # Source code
│   │   ├── App.tsx        # Main React component
│   │   ├── components/    # React components
│   │   ├── services/      # API services
│   ├── package.json       # NPM dependencies
│   └── vite.config.ts     # Vite configuration
│
├── infrastructure/        # Infrastructure as Code
│   └── cloudformation/    # CloudFormation templates
│       ├── vpc.yml        # VPC and networking
│       ├── s3.yml         # S3 buckets
│       ├── batch.yml      # AWS Batch resources
│       └── cognito.yml    # User authentication
│
├── docker/                # Docker configuration
│   ├── Dockerfile.api     # API Docker image
│   ├── Dockerfile.optimizer # Optimization Docker image for AWS Batch
│   └── Dockerfile.worker  # Worker Docker image
│
├── docs/                  # Documentation
├── docker-compose.yml     # Full development setup
└── docker-compose.lite.yml # Lightweight development setup
```

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.9+
- Docker and Docker Compose
- AWS account with access to S3, SQS, Batch, Cognito, and IAM
- AWS CLI configured with appropriate permissions
- Gurobi license (for production deployment)

### AWS Resource Setup

1. **Set up AWS services:**
   - Create an S3 bucket for data storage (e.g., `chico-high-school-optimization`)
   - Create an SQS queue for job processing (e.g., `echelon-jobs`)
   - Set up AWS Batch compute environment and job queue
   - Create IAM roles with appropriate permissions

2. **Configure IAM Role:**
   - Attach policies for S3, SQS, Batch, and CloudWatch access
   - Use the provided `check_aws_permissions.sh` script to verify permissions

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Echelon
   ```

2. **Configure AWS credentials:**
   ```bash
   aws configure
   ```

3. **Edit docker-compose.yml:**
   - Update S3 bucket name
   - Update SQS queue URL
   - Update AWS Batch resources
   - Set your EC2 public IP for the frontend

4. **Start the development environment:**
   ```bash
   docker-compose up --build
   ```

   This will start:
   - PostgreSQL database
   - Backend API service
   - Worker service for job processing
   - Frontend development server

5. **Initialize the database:**
   ```bash
   docker-compose exec api python db_migrations.py create
   docker-compose exec api python db_migrations.py seed
   ```

6. **Access the application:**
   - Frontend: http://your-ec2-ip:5173
   - Backend API: http://your-ec2-ip:8000
   - Adminer database interface: http://your-ec2-ip:8080 (login with postgres/postgres)

### Production Deployment

For production environments, we use the AWS CloudFormation templates in the `infrastructure/` directory:

1. **Deploy CloudFormation stacks:**
   ```bash
   aws cloudformation create-stack --stack-name echelon-platform --template-url s3://echelon-cloudformation/master.yml
   ```

2. **Build and push Docker images:**
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin {account-id}.dkr.ecr.{region}.amazonaws.com
   docker build -t {account-id}.dkr.ecr.{region}.amazonaws.com/echelon-optimization:latest -f docker/Dockerfile.optimizer .
   docker push {account-id}.dkr.ecr.{region}.amazonaws.com/echelon-optimization:latest
   ```

3. **Configure environment variables for production services**

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
  - `SPED`: Indicates special education status (1 for SPED, 0 otherwise)

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
  - `period_name`: Name of the period

## Optimization Process and Workflow

The Echelon platform follows this workflow:

1. **Data Ingestion**: User uploads CSV files with school-specific data through the web interface
2. **File Validation**: Backend API validates files and stores them in S3
3. **Job Creation**: A job is created and added to the SQS queue
4. **Optimization Process**:
   - **Initial Solution**: Greedy algorithm creates a feasible initial solution
   - **Solution Refinement**: Mixed Integer Linear Programming (MILP) refines to optimality
   - **Soft Constraints**: Handles preferences and requirements with varying priorities
5. **Results Generation**: Creates optimized schedules for sections, teachers, and students
6. **Results Delivery**: User can view and download the optimized schedules

### High-Performance Computing

The optimization uses AWS Batch to run computationally intensive jobs:

1. **AWS Batch Compute Environment**: Uses r6i.24xlarge instances with 96 vCPUs and high memory
2. **Docker Containers**: Packaged optimization code runs in isolated containers
3. **Gurobi Solver**: Commercial-grade mathematical optimization software
4. **Dynamic Scaling**: AWS Batch automatically scales resources based on job requirements

### Chico High School Specific Configuration

The system includes specific constraints for Chico High School:

1. **Period Structure**: Uses 8 periods in the schedule (R1-R4, G1-G4)
2. **Course Restrictions**:
   - Medical Career courses can only be scheduled in periods R1 or G1
   - Heroes Teach courses can only be scheduled in periods R2 or G2
3. **Special Education**: Distribution of SPED students is limited to maximum 12 per section
4. **Science Lab Scheduling**: Avoids scheduling science labs in consecutive periods

For detailed information specific to Chico High School, see the [CHICO_HIGH.md](docs/CHICO_HIGH.md) documentation.

### Resource Requirements

The application is designed to operate in various environments:

- **Development**: EC2 instance with 2+ CPUs, 8+ GB RAM
- **API & Worker**: Minimal footprint (500MB RAM per service)
- **Optimization**: Uses AWS Batch with high-memory instances (96+ vCPUs, 384+ GB RAM)
- **Database**: PostgreSQL with modest storage requirements

### Monitoring and Maintenance

The system includes tools for monitoring and troubleshooting:

- **CloudWatch Logs**: All services log to CloudWatch for centralized monitoring
- **Health Checks**: API endpoints for checking service status
- **Debug Utilities**: Tools for diagnosing permissions and connectivity issues
- **Admin Dashboard**: Web interface for monitoring job status and system health

## Security and Compliance

- **Data Encryption**: All data encrypted in transit and at rest
- **Authentication**: AWS Cognito for secure user authentication
- **Authorization**: Role-based access control for different user types
- **Audit Logging**: All system actions are logged for compliance and troubleshooting

## License

All rights reserved © 2025 Echelon Optimization Platform