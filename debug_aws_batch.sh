#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Usage information
usage() {
  echo "Usage: $0 [command] [options]"
  echo ""
  echo "Commands:"
  echo "  list-jobs        List recent AWS Batch jobs"
  echo "  job-details      Show details for a specific job"
  echo "  logs             Get CloudWatch logs for a job"
  echo "  describe-queue   Show information about job queue"
  echo "  describe-ce      Show information about compute environment"
  echo "  list-images      List ECR images"
  echo ""
  echo "Options:"
  echo "  --job-id         AWS Batch job ID (for job-details and logs commands)"
  echo "  --queue          Job queue name (default: echelon-job-queue)"
  echo "  --ce             Compute environment name (default: echelon-compute-environment)"
  echo "  --status         Job status filter (default: all)"
  echo "  --limit          Maximum number of jobs to return (default: 10)"
  echo "  --log-stream     Log stream name (for logs command, instead of job-id)"
  echo ""
  echo "Examples:"
  echo "  $0 list-jobs --status FAILED --limit 5"
  echo "  $0 job-details --job-id 0a1b2c3d-4e5f-6789-0a1b-2c3d4e5f6789"
  echo "  $0 logs --job-id 0a1b2c3d-4e5f-6789-0a1b-2c3d4e5f6789"
  echo "  $0 describe-queue --queue echelon-job-queue"
}

# Check if AWS CLI is installed
check_aws_cli() {
  if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
    exit 1
  fi
}

# List AWS Batch jobs
list_jobs() {
  local queue="$1"
  local status="$2"
  local limit="$3"
  
  echo -e "${GREEN}Listing AWS Batch jobs in queue $queue${NC}"
  
  if [ "$status" == "all" ]; then
    aws batch list-jobs --job-queue "$queue" --max-items "$limit"
  else
    aws batch list-jobs --job-queue "$queue" --job-status "$status" --max-items "$limit"
  fi
}

# Show AWS Batch job details
job_details() {
  local job_id="$1"
  
  echo -e "${GREEN}Getting details for job $job_id${NC}"
  aws batch describe-jobs --jobs "$job_id"
}

# Get CloudWatch logs for a job
get_logs() {
  local job_id="$1"
  local log_stream="$2"
  
  if [ -z "$log_stream" ]; then
    echo -e "${GREEN}Getting log stream name for job $job_id${NC}"
    log_stream=$(aws batch describe-jobs --jobs "$job_id" | grep -o '"logStreamName": "[^"]*' | cut -d'"' -f4)
    
    if [ -z "$log_stream" ]; then
      echo -e "${RED}No log stream found for job $job_id${NC}"
      exit 1
    fi
    
    echo -e "${YELLOW}Log stream: $log_stream${NC}"
  fi
  
  echo -e "${GREEN}Getting CloudWatch logs from /aws/batch/job/$log_stream${NC}"
  aws logs get-log-events --log-group-name "/aws/batch/job" --log-stream-name "$log_stream" | \
    jq -r '.events[] | [(.timestamp | tonumber | . / 1000 | todate), .message] | @tsv'
}

# Describe job queue
describe_queue() {
  local queue="$1"
  
  echo -e "${GREEN}Describing job queue $queue${NC}"
  aws batch describe-job-queues --job-queues "$queue"
}

# Describe compute environment
describe_ce() {
  local ce="$1"
  
  echo -e "${GREEN}Describing compute environment $ce${NC}"
  aws batch describe-compute-environments --compute-environments "$ce"
}

# List ECR images
list_images() {
  echo -e "${GREEN}Listing ECR repositories${NC}"
  aws ecr describe-repositories
  
  echo ""
  echo -e "${YELLOW}To list images in a specific repository, run:${NC}"
  echo "aws ecr describe-images --repository-name REPOSITORY_NAME"
}

# Parse arguments
COMMAND=""
JOB_ID=""
QUEUE="echelon-job-queue"
CE="echelon-compute-environment"
STATUS="all"
LIMIT=10
LOG_STREAM=""

if [ $# -eq 0 ]; then
  usage
  exit 0
fi

COMMAND="$1"
shift

while [ $# -gt 0 ]; do
  case "$1" in
    --job-id)
      JOB_ID="$2"
      shift 2
      ;;
    --queue)
      QUEUE="$2"
      shift 2
      ;;
    --ce)
      CE="$2"
      shift 2
      ;;
    --status)
      STATUS="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --log-stream)
      LOG_STREAM="$2"
      shift 2
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      usage
      exit 1
      ;;
  esac
done

# Execute command
check_aws_cli

case "$COMMAND" in
  list-jobs)
    list_jobs "$QUEUE" "$STATUS" "$LIMIT"
    ;;
  job-details)
    if [ -z "$JOB_ID" ]; then
      echo -e "${RED}Missing required parameter: --job-id${NC}"
      exit 1
    fi
    job_details "$JOB_ID"
    ;;
  logs)
    if [ -z "$JOB_ID" ] && [ -z "$LOG_STREAM" ]; then
      echo -e "${RED}Missing required parameter: --job-id or --log-stream${NC}"
      exit 1
    fi
    get_logs "$JOB_ID" "$LOG_STREAM"
    ;;
  describe-queue)
    describe_queue "$QUEUE"
    ;;
  describe-ce)
    describe_ce "$CE"
    ;;
  list-images)
    list_images
    ;;
  *)
    echo -e "${RED}Unknown command: $COMMAND${NC}"
    usage
    exit 1
    ;;
esac