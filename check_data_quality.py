#!/usr/bin/env python
import boto3
import argparse
import pandas as pd
import io
import sys
from tabulate import tabulate

def get_s3_file(bucket, key):
    """Get file content from S3"""
    s3 = boto3.client('s3')
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        return content
    except Exception as e:
        print(f"Error getting file from S3: {str(e)}")
        return None

def analyze_sections_file(content):
    """Analyze sections file for data quality issues"""
    try:
        df = pd.read_csv(io.BytesIO(content))
        print(f"Sections file contains {len(df)} rows")
        
        # Check required columns
        required_cols = ["section_id", "course_name", "capacity"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"WARNING: Missing required columns: {', '.join(missing_cols)}")
        
        # Print column summary
        print("\nColumns and data types:")
        for col in df.columns:
            print(f"- {col}: {df[col].dtype}")
        
        # Check for NaN values
        nan_counts = df.isna().sum()
        nan_cols = [col for col in df.columns if nan_counts[col] > 0]
        if nan_cols:
            print("\nWARNING: Columns with missing values:")
            for col in nan_cols:
                print(f"- {col}: {nan_counts[col]} missing values")
        
        # Check for duplicates
        if "section_id" in df.columns:
            dup_sections = df[df.duplicated("section_id", keep=False)]
            if not dup_sections.empty:
                print(f"\nWARNING: Found {len(dup_sections)} duplicate section_id values!")
                print(tabulate(dup_sections, headers="keys", tablefmt="grid"))
        
        # Summary stats for capacity
        if "capacity" in df.columns:
            print("\nCapacity statistics:")
            print(f"- Min: {df['capacity'].min()}")
            print(f"- Max: {df['capacity'].max()}")
            print(f"- Mean: {df['capacity'].mean():.2f}")
            print(f"- Zero capacity sections: {len(df[df['capacity'] == 0])}")
        
        # Print sample rows
        print("\nSample data:")
        print(tabulate(df.head(5), headers="keys", tablefmt="grid"))
        
        return df
    except Exception as e:
        print(f"Error analyzing sections file: {str(e)}")
        return None

def analyze_students_file(content):
    """Analyze students file for data quality issues"""
    try:
        df = pd.read_csv(io.BytesIO(content))
        print(f"Students file contains {len(df)} rows")
        
        # Check required columns
        required_cols = ["student_id", "grade_level"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"WARNING: Missing required columns: {', '.join(missing_cols)}")
        
        # Print column summary
        print("\nColumns and data types:")
        for col in df.columns:
            print(f"- {col}: {df[col].dtype}")
        
        # Check for NaN values
        nan_counts = df.isna().sum()
        nan_cols = [col for col in df.columns if nan_counts[col] > 0]
        if nan_cols:
            print("\nWARNING: Columns with missing values:")
            for col in nan_cols:
                print(f"- {col}: {nan_counts[col]} missing values")
        
        # Check for duplicates
        if "student_id" in df.columns:
            dup_students = df[df.duplicated("student_id", keep=False)]
            if not dup_students.empty:
                print(f"\nWARNING: Found {len(dup_students)} duplicate student_id values!")
                print(tabulate(dup_students, headers="keys", tablefmt="grid"))
        
        # Grade level distribution
        if "grade_level" in df.columns:
            print("\nGrade level distribution:")
            grade_counts = df['grade_level'].value_counts().sort_index()
            for grade, count in grade_counts.items():
                print(f"- Grade {grade}: {count} students")
        
        # Print sample rows
        print("\nSample data:")
        print(tabulate(df.head(5), headers="keys", tablefmt="grid"))
        
        return df
    except Exception as e:
        print(f"Error analyzing students file: {str(e)}")
        return None

def analyze_teachers_file(content):
    """Analyze teachers file for data quality issues"""
    try:
        df = pd.read_csv(io.BytesIO(content))
        print(f"Teachers file contains {len(df)} rows")
        
        # Check required columns
        required_cols = ["teacher_id", "name"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"WARNING: Missing required columns: {', '.join(missing_cols)}")
        
        # Print column summary
        print("\nColumns and data types:")
        for col in df.columns:
            print(f"- {col}: {df[col].dtype}")
        
        # Check for NaN values
        nan_counts = df.isna().sum()
        nan_cols = [col for col in df.columns if nan_counts[col] > 0]
        if nan_cols:
            print("\nWARNING: Columns with missing values:")
            for col in nan_cols:
                print(f"- {col}: {nan_counts[col]} missing values")
        
        # Check for duplicates
        if "teacher_id" in df.columns:
            dup_teachers = df[df.duplicated("teacher_id", keep=False)]
            if not dup_teachers.empty:
                print(f"\nWARNING: Found {len(dup_teachers)} duplicate teacher_id values!")
                print(tabulate(dup_teachers, headers="keys", tablefmt="grid"))
        
        # Check for unavailable periods
        if "unavailable_periods" in df.columns:
            print("\nUnavailable periods summary:")
            teachers_with_unavail = df[df['unavailable_periods'].notna()].shape[0]
            print(f"- {teachers_with_unavail} teachers have unavailable periods")
            
            # Parse and validate unavailable periods format
            try:
                df['parsed_unavail'] = df['unavailable_periods'].apply(
                    lambda x: [] if pd.isna(x) else [int(p.strip()) for p in str(x).split(',') if p.strip()]
                )
                
                periods = set()
                for p_list in df['parsed_unavail']:
                    periods.update(p_list)
                
                print(f"- Periods referenced in unavailable_periods: {sorted(periods)}")
            except Exception as e:
                print(f"WARNING: Error parsing unavailable_periods: {str(e)}")
        
        # Print sample rows
        print("\nSample data:")
        print(tabulate(df.head(5), headers="keys", tablefmt="grid"))
        
        return df
    except Exception as e:
        print(f"Error analyzing teachers file: {str(e)}")
        return None

def analyze_preferences_file(content):
    """Analyze preferences file for data quality issues"""
    try:
        df = pd.read_csv(io.BytesIO(content))
        print(f"Preferences file contains {len(df)} rows")
        
        # Check required columns
        required_cols = ["student_id", "section_id", "preference_rank"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"WARNING: Missing required columns: {', '.join(missing_cols)}")
        
        # Print column summary
        print("\nColumns and data types:")
        for col in df.columns:
            print(f"- {col}: {df[col].dtype}")
        
        # Check for NaN values
        nan_counts = df.isna().sum()
        nan_cols = [col for col in df.columns if nan_counts[col] > 0]
        if nan_cols:
            print("\nWARNING: Columns with missing values:")
            for col in nan_cols:
                print(f"- {col}: {nan_counts[col]} missing values")
        
        # Check preference ranks
        if "preference_rank" in df.columns:
            print("\nPreference rank statistics:")
            print(f"- Min rank: {df['preference_rank'].min()}")
            print(f"- Max rank: {df['preference_rank'].max()}")
            rank_counts = df['preference_rank'].value_counts().sort_index()
            print("\nPreference rank distribution:")
            for rank, count in rank_counts.items():
                print(f"- Rank {rank}: {count} preferences")
        
        # Check for duplicate student-section combinations
        if all(col in df.columns for col in ["student_id", "section_id"]):
            dup_prefs = df[df.duplicated(["student_id", "section_id"], keep=False)]
            if not dup_prefs.empty:
                print(f"\nWARNING: Found {len(dup_prefs)} duplicate student-section combinations!")
                print(tabulate(dup_prefs, headers="keys", tablefmt="grid"))
        
        # Check preference counts per student
        if "student_id" in df.columns:
            pref_counts = df['student_id'].value_counts()
            print("\nPreferences per student:")
            print(f"- Min: {pref_counts.min()}")
            print(f"- Max: {pref_counts.max()}")
            print(f"- Mean: {pref_counts.mean():.2f}")
            
            # Students with too few or too many preferences
            low_prefs = pref_counts[pref_counts < 5].shape[0]
            high_prefs = pref_counts[pref_counts > 15].shape[0]
            if low_prefs > 0:
                print(f"WARNING: {low_prefs} students have fewer than 5 preferences")
            if high_prefs > 0:
                print(f"WARNING: {high_prefs} students have more than 15 preferences")
        
        # Print sample rows
        print("\nSample data:")
        print(tabulate(df.head(5), headers="keys", tablefmt="grid"))
        
        return df
    except Exception as e:
        print(f"Error analyzing preferences file: {str(e)}")
        return None

def cross_reference_files(sections_df, students_df, teachers_df, preferences_df):
    """Cross-reference files to check for data consistency issues"""
    if sections_df is None or students_df is None or preferences_df is None:
        print("Cannot cross-reference files: missing required data")
        return
    
    print("\n=== CROSS-REFERENCE VALIDATION ===")
    
    # Check that all sections in preferences exist in sections file
    if all(df is not None for df in [sections_df, preferences_df]):
        if all(col in sections_df.columns for col in ["section_id"]) and all(col in preferences_df.columns for col in ["section_id"]):
            section_ids = set(sections_df['section_id'])
            pref_section_ids = set(preferences_df['section_id'])
            
            missing_sections = pref_section_ids - section_ids
            if missing_sections:
                print(f"WARNING: {len(missing_sections)} section IDs in preferences file don't exist in sections file!")
                print(f"First 10 missing section IDs: {list(missing_sections)[:10]}")
    
    # Check that all students in preferences exist in students file
    if all(df is not None for df in [students_df, preferences_df]):
        if all(col in students_df.columns for col in ["student_id"]) and all(col in preferences_df.columns for col in ["student_id"]):
            student_ids = set(students_df['student_id'])
            pref_student_ids = set(preferences_df['student_id'])
            
            missing_students = pref_student_ids - student_ids
            if missing_students:
                print(f"WARNING: {len(missing_students)} student IDs in preferences file don't exist in students file!")
                print(f"First 10 missing student IDs: {list(missing_students)[:10]}")
    
    # Check section assignments per teacher (if teacher info is in sections file)
    if sections_df is not None and teachers_df is not None:
        if all(col in sections_df.columns for col in ["teacher_id"]):
            teacher_ids = set(teachers_df['teacher_id']) if 'teacher_id' in teachers_df.columns else set()
            section_teacher_ids = set(sections_df['teacher_id'].dropna())
            
            missing_teachers = section_teacher_ids - teacher_ids
            if missing_teachers and teacher_ids:  # Only check if teacher_ids is not empty
                print(f"WARNING: {len(missing_teachers)} teacher IDs in sections file don't exist in teachers file!")
                print(f"First 10 missing teacher IDs: {list(missing_teachers)[:10]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check data quality for school optimization files')
    parser.add_argument('--bucket', default='echelon-uploads', help='S3 bucket name')
    parser.add_argument('--prefix', required=True, help='S3 prefix (e.g., school_id/uploads/timestamp/)')
    
    args = parser.parse_args()
    
    bucket = args.bucket
    prefix = args.prefix
    if not prefix.endswith('/'):
        prefix += '/'
    
    # Get files from S3
    sections_content = get_s3_file(bucket, f"{prefix}sections/sections.csv")
    students_content = get_s3_file(bucket, f"{prefix}students/students.csv")
    teachers_content = get_s3_file(bucket, f"{prefix}teachers/teachers.csv")
    preferences_content = get_s3_file(bucket, f"{prefix}preferences/preferences.csv")
    
    # Analyze each file
    print("\n=== ANALYZING SECTIONS FILE ===")
    sections_df = analyze_sections_file(sections_content) if sections_content else None
    
    print("\n=== ANALYZING STUDENTS FILE ===")
    students_df = analyze_students_file(students_content) if students_content else None
    
    print("\n=== ANALYZING TEACHERS FILE ===")
    teachers_df = analyze_teachers_file(teachers_content) if teachers_content else None
    
    print("\n=== ANALYZING PREFERENCES FILE ===")
    preferences_df = analyze_preferences_file(preferences_content) if preferences_content else None
    
    # Cross-reference files
    cross_reference_files(sections_df, students_df, teachers_df, preferences_df)