#!/bin/bash
# AWS IAM Role Permission Checker for Echelon
# This script helps diagnose IAM role permissions

echo "=== ECHELON AWS PERMISSION CHECKER ==="
echo "Checking AWS credentials and permissions..."
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Installing..."
    pip install awscli
else
    echo "✅ AWS CLI is installed"
fi

echo ""
echo "=== IDENTITY CHECK ==="
# Check if we have an IAM role or credentials
echo "Checking IAM identity..."
if aws sts get-caller-identity 2>/dev/null; then
    echo "✅ Successfully authenticated with AWS"
    
    # Extract and display account info
    ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
    ROLE_NAME=$(aws sts get-caller-identity --query "Arn" --output text | awk -F'/' '{print $2}')
    
    echo "Account ID: $ACCOUNT_ID"
    echo "Role/User: $ROLE_NAME"
    
    # Update docker-compose with the account ID
    if [ -n "$ACCOUNT_ID" ]; then
        echo "Updating docker-compose.yml with your Account ID..."
        sed -i "s/ACCOUNT_ID/$ACCOUNT_ID/g" docker-compose.yml
    fi
else
    echo "❌ Failed to authenticate with AWS"
    echo "    - Check that your EC2 instance has an IAM role attached"
    echo "    - You can attach a role in EC2 console → Actions → Security → Modify IAM Role"
    exit 1
fi

echo ""
echo "=== S3 PERMISSIONS ==="
# Check S3 access
echo "Checking S3 permissions..."
if aws s3 ls &>/dev/null; then
    echo "✅ S3 list operation successful"
    
    # Check if our bucket exists
    BUCKET="echelon-optimization-data"
    if aws s3 ls "s3://$BUCKET" 2>/dev/null; then
        echo "✅ Bucket '$BUCKET' exists and is accessible"
        
        # Test write permissions by uploading a test file
        echo "test" > /tmp/test.txt
        if aws s3 cp /tmp/test.txt "s3://$BUCKET/permissions-test.txt" 2>/dev/null; then
            echo "✅ Successfully wrote to S3 bucket"
            # Clean up
            aws s3 rm "s3://$BUCKET/permissions-test.txt" &>/dev/null
        else
            echo "❌ Cannot write to S3 bucket"
            echo "    - Your IAM role needs s3:PutObject permission"
        fi
    else
        echo "❌ Bucket '$BUCKET' does not exist or is not accessible"
        echo "    - Create the bucket: aws s3 mb s3://$BUCKET"
        echo "    - Or check your IAM role has s3:ListBucket permission"
    fi
else
    echo "❌ Cannot list S3 buckets"
    echo "    - Your IAM role needs s3:ListAllMyBuckets permission"
fi

echo ""
echo "=== SQS PERMISSIONS ==="
# Check SQS access
echo "Checking SQS permissions..."
if aws sqs list-queues &>/dev/null; then
    echo "✅ SQS list operation successful"
    
    # Check if our queue exists
    QUEUE_NAME="echelon-jobs"
    QUEUE_URL=$(aws sqs get-queue-url --queue-name $QUEUE_NAME --query 'QueueUrl' --output text 2>/dev/null)
    
    if [ -n "$QUEUE_URL" ]; then
        echo "✅ Queue '$QUEUE_NAME' exists and is accessible"
        echo "Queue URL: $QUEUE_URL"
        
        # Update docker-compose with the queue URL
        if [ -n "$QUEUE_URL" ]; then
            echo "Updating docker-compose.yml with your Queue URL..."
            sed -i "s|https://sqs.us-west-2.amazonaws.com/ACCOUNT_ID/echelon-jobs|$QUEUE_URL|g" docker-compose.yml
        fi
        
        # Test sending a message
        if aws sqs send-message --queue-url $QUEUE_URL --message-body '{"test":"message"}' &>/dev/null; then
            echo "✅ Successfully sent message to SQS queue"
        else
            echo "❌ Cannot send messages to SQS queue"
            echo "    - Your IAM role needs sqs:SendMessage permission"
        fi
    else
        echo "❌ Queue '$QUEUE_NAME' does not exist or is not accessible"
        echo "    - Create the queue: aws sqs create-queue --queue-name $QUEUE_NAME"
        echo "    - Or check your IAM role has sqs:GetQueueUrl permission"
    fi
else
    echo "❌ Cannot list SQS queues"
    echo "    - Your IAM role needs sqs:ListQueues permission"
fi

echo ""
echo "=== BATCH PERMISSIONS ==="
# Check Batch access
echo "Checking AWS Batch permissions..."
if aws batch describe-job-queues &>/dev/null; then
    echo "✅ Batch describe operation successful"
    
    # Check if our job queue exists
    JOB_QUEUE="echelon-optimization-queue"
    if aws batch describe-job-queues --job-queues $JOB_QUEUE 2>/dev/null | grep -q $JOB_QUEUE; then
        echo "✅ Job queue '$JOB_QUEUE' exists and is accessible"
        
        # Check job definition
        JOB_DEF="echelon-optimization-job"
        if aws batch describe-job-definitions --job-definition-name $JOB_DEF --status ACTIVE 2>/dev/null | grep -q $JOB_DEF; then
            echo "✅ Job definition '$JOB_DEF' exists and is accessible"
        else
            echo "❌ Job definition '$JOB_DEF' does not exist or is not accessible"
            echo "    - Create the job definition using CloudFormation or AWS Console"
            echo "    - Or check your IAM role has batch:DescribeJobDefinitions permission"
        fi
    else
        echo "❌ Job queue '$JOB_QUEUE' does not exist or is not accessible"
        echo "    - Create the job queue using CloudFormation or AWS Console"
        echo "    - Or check your IAM role has batch:DescribeJobQueues permission"
    fi
else
    echo "❌ Cannot access AWS Batch"
    echo "    - Your IAM role needs batch:DescribeJobQueues permission"
fi

echo ""
echo "=== SUMMARY ==="
echo "Check the above results for any ❌ errors that need to be addressed."
echo "After fixing permissions, run your application with:"
echo "sudo docker-compose down"
echo "sudo docker-compose up --build"
echo ""
echo "Your EC2 public IP should be updated in docker-compose.yml"
echo "(Replace EC2_PUBLIC_IP with your actual public IP)"