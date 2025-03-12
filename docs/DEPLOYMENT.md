# Deployment Guide

## AWS Deployment

### Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed
- AWS account with access to:
  - S3
  - CloudFormation
  - ECR
  - Lambda
  - API Gateway
  - Cognito
  - RDS
  - SQS
  - AWS Batch

### Deployment Steps

1. **Set environment variables**

```bash
# Set AWS account and region
export AWS_ACCOUNT_ID=your-account-id
export AWS_REGION=us-west-2
```

2. **Create S3 bucket for CloudFormation templates**

```bash
aws s3 mb s3://echelon-cloudformation --region $AWS_REGION
```

3. **Upload CloudFormation templates**

```bash
aws s3 cp infrastructure/cloudformation/ s3://echelon-cloudformation/ --recursive
```

4. **Deploy the CloudFormation master stack**

```bash
aws cloudformation create-stack \
  --stack-name echelon-platform \
  --template-url https://echelon-cloudformation.s3.amazonaws.com/master.yml \
  --parameters \
    ParameterKey=EnvironmentName,ParameterValue=dev \
    ParameterKey=DatabasePassword,ParameterValue=YourSecurePassword \
    ParameterKey=AdminEmail,ParameterValue=admin@example.com \
    ParameterKey=GurobiLicenseServer,ParameterValue=your-license-server \
  --capabilities CAPABILITY_IAM
```

5. **Create ECR repositories**

```bash
aws ecr create-repository --repository-name echelon-api
aws ecr create-repository --repository-name echelon-optimization
```

6. **Build and push Docker images**

```bash
# Get ECR login
aws ecr get-login-password | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build and push API image
docker build -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/echelon-api:latest -f docker/Dockerfile.api .
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/echelon-api:latest

# Build and push worker image
docker build -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/echelon-optimization:latest -f docker/Dockerfile.worker .
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/echelon-optimization:latest
```

7. **Deploy frontend**

```bash
# Build frontend
cd frontend
npm install
npm run build

# Upload to S3
aws s3 cp dist/ s3://dev-echelon-website/ --recursive
```

## Configuration

### Environment Variables

The following environment variables are used by the application:

#### Backend API

- `S3_BUCKET_NAME`: Bucket for file storage
- `SQS_QUEUE_URL`: URL for the SQS job queue
- `COGNITO_USER_POOL_ID`: Cognito user pool ID
- `COGNITO_APP_CLIENT_ID`: Cognito app client ID
- `DATABASE_URL`: PostgreSQL connection string

#### Optimization Worker

- `USE_S3`: Set to "true" to use S3 for data storage
- `BUCKET_NAME`: S3 bucket for optimization data
- `SCHOOL_PREFIX`: S3 prefix for school data
- `SCHOOL_ID`: School identifier
- `GUROBI_LICENSE_SERVER`: Address of Gurobi license server

## Monitoring

### CloudWatch Logs

The application logs to CloudWatch Logs with the following log groups:

- `/aws/lambda/echelon-api-function`: API execution logs
- `/aws/batch/job`: Batch job execution logs

### CloudWatch Metrics

Custom metrics are published to CloudWatch:

- `OptimizationJobDuration`: Duration of optimization jobs
- `OptimizationSatisfactionRate`: Percentage of student requests satisfied
- `ApiRequests`: Count of API requests
- `ApiErrors`: Count of API errors

## Backup and Recovery

### Database Backups

RDS automated backups are enabled with:
- Backup retention period: 7 days
- Backup window: 03:00-05:00 UTC

### S3 Backup

S3 versioning is enabled on all buckets to protect against accidental deletions.

## Security

### Network Security

- All services run within a VPC with private subnets
- Access to services is controlled via security groups
- API Gateway uses AWS IAM and Cognito for authentication

### Data Security

- S3 SSE (Server-Side Encryption) is enabled for all buckets
- RDS encryption is enabled
- All data in transit is encrypted using TLS

### Authentication

- Cognito user pools provide secure user authentication
- JWT tokens are used for API authentication
- Role-based access control is implemented in the backend API