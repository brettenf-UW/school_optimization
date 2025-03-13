#!/bin/bash
# Setup script for Echelon resources

echo "=== SETTING UP AWS RESOURCES FOR ECHELON ==="

# Check AWS CLI and identity
echo "Checking AWS identity..."
aws sts get-caller-identity

# Create SQS queue if it doesn't exist
echo "Creating SQS queue 'echelon-jobs'..."
QUEUE_URL=$(aws sqs create-queue --queue-name echelon-jobs --query 'QueueUrl' --output text)
echo "Queue created or already exists: $QUEUE_URL"

# Update docker-compose.yml with account ID and queue URL
echo "Updating docker-compose.yml with your AWS Account ID and Queue URL..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
sed -i "s/ACCOUNT_ID/$ACCOUNT_ID/g" docker-compose.yml

echo "=== SETUP COMPLETE ==="
echo "Now run these commands to start your application:"
echo "sudo docker-compose down"
echo "sudo docker-compose up --build"
echo ""
echo "In a new terminal, initialize the database with:"
echo "sudo docker-compose exec api python db_migrations.py create"
echo "sudo docker-compose exec api python db_migrations.py seed"
echo ""
echo "Then access your application at: http://54.202.229.226:5173"