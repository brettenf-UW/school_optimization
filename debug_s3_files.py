#!/usr/bin/env python
import boto3
import argparse
import json
from tabulate import tabulate
import sys

def list_school_files(school_id=None, limit=50):
    """List files in S3 for a specific school or all schools"""
    s3 = boto3.client('s3')
    bucket_name = 'echelon-uploads'  # Update with your bucket name
    
    try:
        if school_id:
            prefix = f"{school_id}/"
        else:
            prefix = ""
        
        response = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix,
            MaxKeys=limit
        )
        
        if 'Contents' not in response:
            print(f"No files found for school_id={school_id}")
            return []
        
        files = []
        for obj in response['Contents']:
            files.append({
                'Key': obj['Key'],
                'Size': obj['Size'],
                'LastModified': obj['LastModified'].strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Print table of files
        print(tabulate(files, headers="keys", tablefmt="grid"))
        
        return files
    except Exception as e:
        print(f"Error listing files: {str(e)}")
        return []

def get_file_content(file_key):
    """Get and display content of a specific file"""
    s3 = boto3.client('s3')
    bucket_name = 'echelon-uploads'  # Update with your bucket name
    
    try:
        response = s3.get_object(
            Bucket=bucket_name,
            Key=file_key
        )
        
        content = response['Body'].read().decode('utf-8')
        
        if file_key.endswith('.json'):
            pretty_content = json.dumps(json.loads(content), indent=2)
            print(pretty_content)
        else:
            print(content)
        
        return content
    except Exception as e:
        print(f"Error getting file content: {str(e)}")
        return None

def list_school_uploads(school_id):
    """List upload timestamps for a specific school"""
    s3 = boto3.client('s3')
    bucket_name = 'echelon-uploads'  # Update with your bucket name
    
    try:
        prefix = f"{school_id}/uploads/"
        
        response = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix,
            Delimiter='/'
        )
        
        if 'CommonPrefixes' not in response:
            print(f"No uploads found for school_id={school_id}")
            return []
        
        uploads = []
        for prefix_obj in response['CommonPrefixes']:
            upload_timestamp = prefix_obj['Prefix'].replace(f"{school_id}/uploads/", "").strip('/')
            uploads.append({
                'Timestamp': upload_timestamp
            })
        
        # Print table of uploads
        print(tabulate(uploads, headers="keys", tablefmt="grid"))
        
        return uploads
    except Exception as e:
        print(f"Error listing uploads: {str(e)}")
        return []

def compare_uploads(school_id, timestamp1, timestamp2):
    """Compare files between two upload timestamps"""
    s3 = boto3.client('s3')
    bucket_name = 'echelon-uploads'  # Update with your bucket name
    
    try:
        prefix1 = f"{school_id}/uploads/{timestamp1}/"
        prefix2 = f"{school_id}/uploads/{timestamp2}/"
        
        # Get files for first timestamp
        response1 = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix1
        )
        
        # Get files for second timestamp
        response2 = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix2
        )
        
        files1 = [obj['Key'].replace(prefix1, '') for obj in response1.get('Contents', [])]
        files2 = [obj['Key'].replace(prefix2, '') for obj in response2.get('Contents', [])]
        
        print(f"Files in {timestamp1}: {len(files1)}")
        print(f"Files in {timestamp2}: {len(files2)}")
        
        # Files only in first upload
        only_in_1 = [f for f in files1 if f not in files2]
        if only_in_1:
            print(f"\nFiles only in {timestamp1}:")
            for f in only_in_1:
                print(f"  - {f}")
        
        # Files only in second upload
        only_in_2 = [f for f in files2 if f not in files1]
        if only_in_2:
            print(f"\nFiles only in {timestamp2}:")
            for f in only_in_2:
                print(f"  - {f}")
        
        # Files in both uploads
        common_files = [f for f in files1 if f in files2]
        if common_files:
            print(f"\nFiles in both uploads:")
            for f in common_files:
                print(f"  - {f}")
    
    except Exception as e:
        print(f"Error comparing uploads: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Debug S3 files for school optimization')
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # List files command
    list_parser = subparsers.add_parser('list', help='List files')
    list_parser.add_argument('--school', help='School ID', required=False)
    list_parser.add_argument('--limit', type=int, default=50, help='Max number of files to list')
    
    # Get file content command
    get_parser = subparsers.add_parser('get', help='Get file content')
    get_parser.add_argument('--key', help='S3 key of the file', required=True)
    
    # List uploads command
    uploads_parser = subparsers.add_parser('uploads', help='List upload timestamps')
    uploads_parser.add_argument('--school', help='School ID', required=True)
    
    # Compare uploads command
    compare_parser = subparsers.add_parser('compare', help='Compare uploads')
    compare_parser.add_argument('--school', help='School ID', required=True)
    compare_parser.add_argument('--t1', help='First timestamp', required=True)
    compare_parser.add_argument('--t2', help='Second timestamp', required=True)
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_school_files(args.school, args.limit)
    elif args.command == 'get':
        get_file_content(args.key)
    elif args.command == 'uploads':
        list_school_uploads(args.school)
    elif args.command == 'compare':
        compare_uploads(args.school, args.t1, args.t2)
    else:
        parser.print_help()
        sys.exit(1)