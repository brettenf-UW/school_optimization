# Echelon: School Scheduling Optimization Platform

A web-based platform for optimizing school master schedules using linear programming techniques.

## Project Overview

Echelon is designed to help schools create optimal master schedules by using advanced optimization algorithms. The platform:

- Allows users to upload CSV files with school-specific data
- Runs advanced optimization using Gurobi solver
- Provides a clean interface for managing optimization jobs and viewing results
- Leverages cloud infrastructure for high-performance computing (48 CPUs, 368GB RAM)
- Ensures security of sensitive school data

## Directory Structure

```
Revised/
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
│   │   └── ...
│   ├── batch_jobs/         # AWS Batch job definitions
│   └── requirements.txt    # Python dependencies
│
├── frontend/              # React frontend application
│   ├── src/               # Source code
│   │   ├── App.tsx        # Main React component
│   │   ├── components/    # React components
│   │   ├── services/      # API services
│   │   └── ...
│   ├── package.json       # NPM dependencies
│   └── vite.config.ts     # Vite configuration
│
├── infrastructure/        # Infrastructure as Code
│   └── cloudformation/    # CloudFormation templates
│       ├── vpc.yml        # VPC and networking
│       ├── s3.yml         # S3 buckets
│       └── ...
│
├── docker/                # Docker configuration
│   ├── Dockerfile.api     # API Docker image
│   └── Dockerfile.worker  # Worker Docker image
│
├── docs/                  # Documentation
└── docker-compose.yml     # Local development setup
```

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.9+
- Docker and Docker Compose
- AWS CLI configured with appropriate permissions
- Gurobi license (for production deployment)

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Revised
   ```

2. **Start the local development environment:**
   ```bash
   docker-compose up --build
   ```

   This will start:
   - PostgreSQL database
   - LocalStack (for AWS services simulation)
   - Backend API
   - Frontend development server

3. **Initialize the database:**
   ```bash
   docker-compose exec api python db_migrations.py create
   docker-compose exec api python db_migrations.py seed
   ```

4. **Access the application:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000

## File Format Requirements

### sections.csv
- Required columns:
  - `section_id`: Unique identifier for the section
  - `course_name`: Name of the course
  - `capacity`: Maximum number of students

### students.csv
- Required columns:
  - `student_id`: Unique identifier for the student
  - `grade_level`: Student's grade level

### teachers.csv
- Required columns:
  - `teacher_id`: Unique identifier for the teacher
  - `name`: Teacher's name

### preferences.csv
- Required columns:
  - `student_id`: Student identifier
  - `section_id`: Section identifier
  - `preference_rank`: Preference ranking (lower is better)

## Optimization Process

The optimization works in two stages:
1. **Greedy Algorithm**: Creates an initial feasible solution
2. **Mixed Integer Linear Programming**: Refines the solution to optimality

### Command-Line Usage

The core optimization can be run directly from the command line:

```bash
# Run with local files
cd core
python milp_soft.py

# Run with S3 integration
python milp_soft.py --use-s3 --bucket-name my-school-data --school-id chico-high-school
```

## License

All rights reserved © 2025 Echelon Optimization Platform