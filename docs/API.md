# API Documentation

## Authentication Endpoints

### Sign In
```
POST /auth/signin
```
Sign in with username and password

**Request Body:**
```json
{
  "username": "user@example.com",
  "password": "password"
}
```

**Response:**
```json
{
  "token": "jwt-token",
  "user": {
    "id": "user-id",
    "email": "user@example.com",
    "name": "User Name",
    "role": "Admin"
  }
}
```

### Change Password
```
POST /auth/change-password
```
Change password for authenticated user

**Request Body:**
```json
{
  "old_password": "old-password",
  "new_password": "new-password"
}
```

## File Upload Endpoints

### Upload School Data
```
POST /api/upload/school-data
```
Upload school data files for optimization

**Request Body (multipart/form-data):**
- `school_id`: ID of the school
- `sections_file`: CSV file with sections data
- `students_file`: CSV file with students data
- `teachers_file`: CSV file with teachers data
- `preferences_file`: CSV file with student preferences

**Response:**
```json
{
  "message": "Files uploaded successfully",
  "upload_id": "20230520_123045",
  "files": {
    "sections": "school-id/uploads/20230520_123045/sections/sections.csv",
    "students": "school-id/uploads/20230520_123045/students/students.csv",
    "teachers": "school-id/uploads/20230520_123045/teachers/teachers.csv",
    "preferences": "school-id/uploads/20230520_123045/preferences/preferences.csv"
  },
  "file_ids": ["file-id-1", "file-id-2", "file-id-3", "file-id-4"]
}
```

## Job Management Endpoints

### Schedule Optimization Job
```
POST /api/jobs/schedule
```
Schedule a new optimization job

**Request Body:**
```json
{
  "name": "Master Schedule Generation",
  "job_type": "master_schedule",
  "school_id": "school-id",
  "file_ids": ["file-id-1", "file-id-2", "file-id-3", "file-id-4"],
  "parameters": {
    "max_runtime_seconds": 14400,
    "use_greedy_initial": true
  },
  "model_id": "model-id"
}
```

**Response:**
```json
{
  "message": "Job scheduled successfully",
  "job_id": "job-id",
  "status": "QUEUED"
}
```

### Get Job Status
```
GET /api/jobs/{job_id}/status
```
Get the status of an optimization job

**Response:**
```json
{
  "job_id": "job-id",
  "name": "Master Schedule Generation",
  "status": "RUNNING",
  "progress": 45,
  "error_message": null,
  "created_at": "2023-05-20T12:30:45Z",
  "started_at": "2023-05-20T12:31:00Z",
  "completed_at": null,
  "school_id": "school-id",
  "user_id": "user-id"
}
```

### Get Job Results
```
GET /api/jobs/{job_id}/results
```
Get the results of a completed optimization job

**Response:**
```json
{
  "job_id": "job-id",
  "name": "Master Schedule Generation",
  "status": "COMPLETED",
  "result_summary": {
    "satisfied_requests": 1200,
    "total_requests": 1250,
    "satisfaction_rate": 96.0,
    "sections_over_capacity": 3,
    "total_overages": 5
  },
  "completed_at": "2023-05-20T14:30:45Z",
  "execution_time": 7200,
  "files": [
    {
      "file_id": "result-file-id-1",
      "name": "Master_Schedule.csv",
      "file_type": "master_schedule",
      "download_url": "https://presigned-url-1"
    },
    {
      "file_id": "result-file-id-2",
      "name": "Student_Assignments.csv",
      "file_type": "student_assignments",
      "download_url": "https://presigned-url-2"
    },
    {
      "file_id": "result-file-id-3",
      "name": "Teacher_Schedule.csv",
      "file_type": "teacher_schedule",
      "download_url": "https://presigned-url-3"
    },
    {
      "file_id": "result-file-id-4",
      "name": "Constraint_Violations.csv",
      "file_type": "constraint_violations",
      "download_url": "https://presigned-url-4"
    }
  ]
}
```

## Admin Endpoints

### List All Jobs
```
GET /api/admin/jobs
```
Admin endpoint to list all jobs across all schools

**Query Parameters:**
- `limit`: Maximum number of jobs to return (default: 50)
- `offset`: Offset for pagination (default: 0)
- `status`: Filter by job status (optional)

**Response:**
```json
{
  "jobs": [
    {
      "id": "job-id-1",
      "name": "Master Schedule Generation",
      "job_type": "master_schedule",
      "status": "COMPLETED",
      "created_at": "2023-05-20T12:30:45Z",
      "school_id": "school-id-1",
      "user_id": "user-id-1"
    },
    {
      "id": "job-id-2",
      "name": "Student Assignment",
      "job_type": "student_assignments",
      "status": "RUNNING",
      "created_at": "2023-05-21T09:15:30Z",
      "school_id": "school-id-2",
      "user_id": "user-id-2"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

### Create User
```
POST /api/admin/users
```
Admin endpoint to create a new user

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "name": "New User",
  "role": "Teacher",
  "school_id": "school-id"
}
```

**Response:**
```json
{
  "message": "User created successfully",
  "user_id": "user-id",
  "cognito_id": "cognito-id"
}
```