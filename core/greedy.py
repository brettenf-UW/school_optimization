import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import time
import logging
import os
from pathlib import Path
import boto3
import io
import argparse

def load_data(input_dir="input", use_s3=False, bucket_name=None, school_prefix=None, school_id=None):
    """Load all necessary data files from local filesystem or S3.
    
    Args:
        input_dir (str): Local directory for input files (if not using S3)
        use_s3 (bool): Whether to use S3 for data storage
        bucket_name (str): S3 bucket name if using S3
        school_prefix (str): S3 prefix for school data if using S3
        school_id (str): School identifier if using S3 (default: chico-high-school)
    """
    # Set default values for S3 parameters
    school_id = school_id or "chico-high-school"
    school_prefix = school_prefix or "input-data"
    
    if use_s3:
        # Initialize S3 client
        s3_client = boto3.client('s3')
        input_path = f"{school_prefix}/{school_id}"
        
        # Read from S3
        try:
            # Define file paths in S3
            students_path = f"{input_path}/students/Student_Info.csv"
            preferences_path = f"{input_path}/students/Student_Preference_Info.csv"
            teachers_path = f"{input_path}/teachers/Teacher_Info.csv"
            sections_path = f"{input_path}/sections/Sections_Information.csv"
            periods_path = f"{input_path}/schedule/Period.csv"
            unavailability_path = f"{input_path}/teachers/Teacher_unavailability.csv"
            
            # Helper function to read CSV from S3
            def read_s3_csv(key):
                try:
                    response = s3_client.get_object(Bucket=bucket_name, Key=key)
                    content = response['Body'].read()
                    return pd.read_csv(io.BytesIO(content))
                except s3_client.exceptions.NoSuchKey:
                    print(f"Warning: File not found in S3: {key}")
                    if key == unavailability_path:
                        # Return empty DataFrame for teacher unavailability if not found
                        return pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
                    else:
                        raise FileNotFoundError(f"Required file not found in S3: {key}")
            
            # Load data from S3
            students = read_s3_csv(students_path)
            student_preferences = read_s3_csv(preferences_path)
            teachers = read_s3_csv(teachers_path)
            sections = read_s3_csv(sections_path)
            
            # Try to load periods, fallback to default periods if not found
            try:
                periods_df = read_s3_csv(periods_path)
                periods = periods_df['period_name'].tolist()
            except (pd.errors.EmptyDataError, FileNotFoundError):
                print(f"Warning: Period file not found in S3, using default periods")
                periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']
            
            # Load teacher unavailability, with robust error handling
            try:
                teacher_unavailability = read_s3_csv(unavailability_path)
            except (pd.errors.EmptyDataError, FileNotFoundError):
                teacher_unavailability = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
                print(f"Warning: Teacher unavailability file not found in S3, using empty DataFrame")
                
        except Exception as e:
            print(f"Error loading data from S3: {str(e)}")
            raise
    else:
        # Load from local filesystem
        students = pd.read_csv(f"{input_dir}/Student_Info.csv")
        student_preferences = pd.read_csv(f"{input_dir}/Student_Preference_Info.csv")
        teachers = pd.read_csv(f"{input_dir}/Teacher_Info.csv")
        sections = pd.read_csv(f"{input_dir}/Sections_Information.csv")
        
        # Load periods
        try:
            periods_df = pd.read_csv(f"{input_dir}/Period.csv")
            periods = periods_df['period_name'].tolist()
        except (pd.errors.EmptyDataError, FileNotFoundError):
            periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']
        
        # Robust teacher unavailability loading
        try:
            teacher_unavailability = pd.read_csv(f"{input_dir}/Teacher_unavailability.csv")
            if teacher_unavailability.empty:
                teacher_unavailability = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
        except (pd.errors.EmptyDataError, FileNotFoundError):
            teacher_unavailability = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
    
    return students, student_preferences, teachers, sections, teacher_unavailability, periods

def preprocess_data(students, student_preferences, teachers, sections, teacher_unavailability, periods):
    """Preprocess data to create useful mappings."""
    # Map courses to sections
    course_to_sections = defaultdict(list)
    for _, row in sections.iterrows():
        course_to_sections[row['Course ID']].append(row['Section ID'])
    
    # Create section capacity mapping
    section_capacity = sections.set_index('Section ID')['# of Seats Available'].to_dict()
    
    # Map teachers to sections
    teacher_to_sections = defaultdict(list)
    for _, row in sections.iterrows():
        teacher_to_sections[row['Teacher Assigned']].append(row['Section ID'])
    
    # Map sections to courses
    section_to_course = sections.set_index('Section ID')['Course ID'].to_dict()
    
    # Map sections to teachers
    section_to_teacher = sections.set_index('Section ID')['Teacher Assigned'].to_dict()
    
    # Map sections to departments
    section_to_dept = sections.set_index('Section ID')['Department'].to_dict()
    
    # Convert teacher unavailability to a mapping
    teacher_unavailable_periods = defaultdict(list)
    for _, row in teacher_unavailability.iterrows():
        if pd.notna(row['Unavailable Periods']):
            teacher_unavailable_periods[row['Teacher ID']] = row['Unavailable Periods'].split(',')
    
    # Map student preferences to a more usable format
    student_pref_courses = {}
    for _, row in student_preferences.iterrows():
        student_pref_courses[row['Student ID']] = row['Preferred Sections'].split(';')
    
    # Identify special course restrictions
    special_course_periods = {
        'Medical Career': ['R1', 'G1'],
        'Heroes Teach': ['R2', 'G2']
    }
    
    # Identify SPED students
    sped_students = set(students[students['SPED'] == 'Yes']['Student ID'].tolist())
    
    return {
        'course_to_sections': course_to_sections,
        'section_capacity': section_capacity,
        'teacher_to_sections': teacher_to_sections,
        'teacher_unavailable_periods': teacher_unavailable_periods,
        'student_pref_courses': student_pref_courses,
        'special_course_periods': special_course_periods,
        'sped_students': sped_students,
        'section_to_course': section_to_course,
        'section_to_teacher': section_to_teacher,
        'section_to_dept': section_to_dept,
        'periods': periods
    }

def compute_section_priority(sections, course_to_sections, special_course_periods, teacher_to_sections, data):
    """Compute a priority score for each section to determine scheduling order."""
    section_priority = {}
    
    for _, row in sections.iterrows():
        section_id = row['Section ID']
        course_id = row['Course ID']
        teacher_id = row['Teacher Assigned']
        
        # Base priority score (higher = schedule earlier)
        priority = 1.0
        
        # Special course sections have highest priority
        if course_id in special_course_periods:
            priority *= 5.0
        
        # Sports Med sections have high priority
        if course_id == 'Sports Med':
            priority *= 3.0
        
        # Science courses have high priority
        if 'Science' in row['Department'] or course_id in ['Biology', 'Chemistry', 'Physics', 'AP Biology']:
            priority *= 2.5
        
        # Teachers with many sections are harder to schedule
        teacher_section_count = len(teacher_to_sections[teacher_id])
        priority *= (1.0 + 0.2 * teacher_section_count)
        
        # Courses with fewer sections are harder to schedule
        course_section_count = len(course_to_sections[course_id])
        priority *= (1.0 + 1.0 / course_section_count)
        
        # Student demand-based priority
        student_demand = sum(1 for prefs in data['student_pref_courses'].values() 
                           if course_id in prefs)
        priority *= (1.0 + 0.001 * student_demand)
        
        section_priority[section_id] = priority
    
    return section_priority

def compute_period_score(section_id, period, scheduled_sections, data):
    """Compute how good a period is for a given section."""
    course_id = data['section_to_course'][section_id]
    teacher_id = data['section_to_teacher'][section_id]
    
    # Start with base score
    score = 1.0
    
    # Special course period restrictions
    if course_id in data['special_course_periods']:
        if period not in data['special_course_periods'][course_id]:
            return 0.0  # Forbidden period
        # If this is a required period and course has no section in it yet, boost score
        course_sections = data['course_to_sections'][course_id]
        period_used = any(s in scheduled_sections and scheduled_sections[s] == period 
                        for s in course_sections)
        if not period_used:
            score *= 2.0  # Boost score for required periods not yet used
    
    # Check teacher unavailability
    if teacher_id in data['teacher_unavailable_periods'] and period in data['teacher_unavailable_periods'][teacher_id]:
        return 0.0  # Unavailable period
    
    # Check teacher conflicts
    for other_section in data['teacher_to_sections'][teacher_id]:
        if other_section in scheduled_sections and scheduled_sections[other_section] == period:
            return 0.0  # Teacher conflict
    
    # Prefer balanced distribution of course sections across periods
    course_sections = data['course_to_sections'][course_id]
    course_period_usage = Counter([scheduled_sections[s] for s in course_sections if s in scheduled_sections])
    if period in course_period_usage:
        score /= (1.0 + 0.5 * course_period_usage[period])  # Lower score if period already has this course
    
    # Prefer balanced distribution of department sections across periods
    dept = data['section_to_dept'].get(section_id)
    if dept:
        dept_sections = [s for s in data['section_to_course'].keys() if data['section_to_dept'].get(s) == dept]
        dept_period_usage = Counter([scheduled_sections[s] for s in dept_sections if s in scheduled_sections])
        if period in dept_period_usage:
            score /= (1.0 + 0.3 * dept_period_usage[period])  # Lower score if period already has this department
    
    # Sports Med constraint: avoid multiple Sports Med sections in same period
    if course_id == 'Sports Med':
        sports_med_sections = [s for s, c in data['section_to_course'].items() if c == 'Sports Med']
        sports_med_period_usage = sum(1 for s in sports_med_sections 
                                     if s in scheduled_sections and scheduled_sections[s] == period)
        if sports_med_period_usage > 0:
            score *= 0.5  # Lower score if period already has Sports Med section
    
    # Science prep time considerations
    if 'Science' in data['section_to_dept'].get(section_id, ''):
        science_sections = [s for s, dept in data['section_to_dept'].items() 
                         if 'Science' in dept and s in scheduled_sections]
        adjacent_periods = get_adjacent_periods(period, data['periods'])
        adjacent_science_count = sum(1 for s in science_sections 
                                    if scheduled_sections[s] in adjacent_periods)
        if adjacent_science_count > 0:
            score *= (0.7 ** adjacent_science_count)  # Lower score for adjacent science sections
    
    # Balancing consideration: prefer periods with fewer sections overall
    period_usage = sum(1 for p in scheduled_sections.values() if p == period)
    score /= (1.0 + 0.1 * period_usage)
    
    return score

def get_adjacent_periods(period, periods):
    """Get adjacent periods for science prep time consideration."""
    period_idx = periods.index(period)
    adjacent = []
    if period_idx > 0:
        adjacent.append(periods[period_idx - 1])
    if period_idx < len(periods) - 1:
        adjacent.append(periods[period_idx + 1])
    return adjacent

def greedy_schedule_sections(sections, periods, data):
    """Schedule sections to periods using a greedy approach prioritizing difficult sections."""
    # Compute section priorities
    section_priority = compute_section_priority(sections, data['course_to_sections'], 
                                             data['special_course_periods'], 
                                             data['teacher_to_sections'], data)
    
    # Sort sections by priority (highest first)
    sorted_sections = sorted(sections['Section ID'].tolist(), key=lambda s: -section_priority.get(s, 0))
    
    # Initialize scheduled sections
    scheduled_sections = {}
    
    # First phase: Schedule special course sections
    for section_id in sorted_sections:
        course_id = data['section_to_course'][section_id]
        if course_id in data['special_course_periods']:
            # For special courses, match to required periods
            best_period = None
            best_score = -1
            
            for period in periods:
                score = compute_period_score(section_id, period, scheduled_sections, data)
                if score > best_score:
                    best_period = period
                    best_score = score
            
            if best_period and best_score > 0:
                scheduled_sections[section_id] = best_period
                print(f"Scheduled special section {section_id} ({course_id}) to period {best_period}")
    
    # Second phase: Schedule Sports Med sections
    for section_id in sorted_sections:
        if section_id in scheduled_sections:
            continue  # Already scheduled
            
        course_id = data['section_to_course'][section_id]
        if course_id == 'Sports Med':
            best_period = None
            best_score = -1
            
            for period in periods:
                score = compute_period_score(section_id, period, scheduled_sections, data)
                if score > best_score:
                    best_period = period
                    best_score = score
            
            if best_period and best_score > 0:
                scheduled_sections[section_id] = best_period
                print(f"Scheduled Sports Med section {section_id} to period {best_period}")
    
    # Third phase: Schedule science sections
    for section_id in sorted_sections:
        if section_id in scheduled_sections:
            continue  # Already scheduled
            
        dept = data['section_to_dept'].get(section_id)
        if dept and 'Science' in dept:
            best_period = None
            best_score = -1
            
            for period in periods:
                score = compute_period_score(section_id, period, scheduled_sections, data)
                if score > best_score:
                    best_period = period
                    best_score = score
            
            if best_period and best_score > 0:
                scheduled_sections[section_id] = best_period
                print(f"Scheduled science section {section_id} to period {best_period}")
    
    # Fourth phase: Schedule remaining sections
    for section_id in sorted_sections:
        if section_id in scheduled_sections:
            continue  # Already scheduled
        
        best_period = None
        best_score = -1
        
        for period in periods:
            score = compute_period_score(section_id, period, scheduled_sections, data)
            if score > best_score:
                best_period = period
                best_score = score
        
        if best_period and best_score > 0:
            scheduled_sections[section_id] = best_period
            print(f"Scheduled section {section_id} to period {best_period}")
        else:
            print(f"WARNING: Could not schedule section {section_id}")
    
    return scheduled_sections

def compute_student_section_score(student_id, section_id, student_assignments, section_assignments, data):
    """Compute score for assigning a student to a section."""
    # Check if student already assigned to this course
    course_id = data['section_to_course'][section_id]
    student_courses = [data['section_to_course'][sec] for sec in student_assignments.get(student_id, [])]
    if course_id in student_courses:
        return 0.0  # Already assigned to this course
    
    # Check if student wants this course
    if course_id not in data['student_pref_courses'].get(student_id, []):
        return 0.0  # Not preferred
    
    # Check for period conflicts
    period = section_assignments.get(section_id)
    if not period:
        return 0.0  # Section not scheduled
    
    student_periods = [section_assignments.get(sec) for sec in student_assignments.get(student_id, [])]
    if period in student_periods:
        return 0.0  # Period conflict
    
    # Check section capacity
    section_students = [s for s, secs in student_assignments.items() if section_id in secs]
    if len(section_students) >= data['section_capacity'].get(section_id, 0):
        return 0.0  # Section full
    
    # Base score
    score = 1.0
    
    # Favor less filled sections
    fill_ratio = len(section_students) / data['section_capacity'].get(section_id, 1)
    score *= (1.1 - fill_ratio)  # Higher score for less filled sections
    
    # SPED distribution - soft constraint
    if student_id in data['sped_students']:
        sped_count = sum(1 for s in section_students if s in data['sped_students'])
        if sped_count >= 2:  # Avoid more than 2 SPED students per section
            score *= (0.5 ** (sped_count - 1))  # Exponential penalty
    
    # Boost score for required courses that student might not get
    remaining_courses = set(data['student_pref_courses'].get(student_id, [])) - set(student_courses)
    remaining_sections = {}
    for c in remaining_courses:
        remaining_sections[c] = [s for s in data['course_to_sections'].get(c, []) 
                                if s in section_assignments]
    
    # Calculate availability score
    availability_score = 1.0
    num_sections_available = len(remaining_sections.get(course_id, []))
    if num_sections_available <= 2:  # Few options left
        availability_score = 2.0  # Boost score
    
    score *= availability_score
    
    return score

def greedy_assign_students(students, scheduled_sections, data):
    """Assign students to sections greedily based on preferences and constraints."""
    # Initialize student assignments
    student_assignments = defaultdict(list)  # student_id -> [section_id, ...]
    
    # Calculate student "hardness" to prioritize difficult students first
    student_hardness = {}
    for student_id in students['Student ID']:
        # SPED students are harder to place
        hardness = 1.0
        if student_id in data['sped_students']:
            hardness *= 2.0
        
        # Students with special courses are harder to place
        if any(c in ['Medical Career', 'Heroes Teach'] 
              for c in data['student_pref_courses'].get(student_id, [])):
            hardness *= 1.5
        
        # Students with many course dependencies are harder to place
        num_courses = len(data['student_pref_courses'].get(student_id, []))
        hardness *= (1.0 + 0.1 * num_courses)
        
        student_hardness[student_id] = hardness
    
    # Sort students by hardness (hardest first)
    sorted_students = sorted(students['Student ID'].tolist(), key=lambda s: -student_hardness.get(s, 0))
    
    # First phase: Assign special courses
    special_courses = ['Medical Career', 'Heroes Teach', 'Sports Med']
    for student_id in sorted_students:
        for course_id in special_courses:
            if course_id not in data['student_pref_courses'].get(student_id, []):
                continue  # Student doesn't want this course
            
            # Get available sections for this course
            available_sections = []
            for section_id in data['course_to_sections'].get(course_id, []):
                if section_id not in scheduled_sections:
                    continue  # Section not scheduled
                
                score = compute_student_section_score(student_id, section_id, 
                                                   student_assignments, scheduled_sections, data)
                if score > 0:
                    available_sections.append((section_id, score))
            
            if available_sections:
                # Choose best section
                best_section = max(available_sections, key=lambda x: x[1])[0]
                student_assignments[student_id].append(best_section)
                print(f"Assigned student {student_id} to special section {best_section} ({course_id})")
    
    # Second phase: Assign non-special courses
    for student_id in sorted_students:
        # Calculate which courses student still needs
        assigned_courses = [data['section_to_course'][sec] for sec in student_assignments.get(student_id, [])]
        needed_courses = [c for c in data['student_pref_courses'].get(student_id, []) 
                        if c not in assigned_courses and c not in special_courses]
        
        # Dictionary to track best section for each needed course
        best_sections = {}
        
        # Find best section for each needed course
        for course_id in needed_courses:
            best_section = None
            best_score = 0
            
            for section_id in data['course_to_sections'].get(course_id, []):
                if section_id not in scheduled_sections:
                    continue  # Section not scheduled
                
                score = compute_student_section_score(student_id, section_id, 
                                                   student_assignments, scheduled_sections, data)
                if score > best_score:
                    best_section = section_id
                    best_score = score
            
            if best_section:
                best_sections[course_id] = (best_section, best_score)
        
        # Sort needed courses by score (best first)
        sorted_courses = sorted(best_sections.keys(), key=lambda c: -best_sections[c][1])
        
        # Assign student to each course in order
        for course_id in sorted_courses:
            section_id = best_sections[course_id][0]
            
            # Check if still valid (no period conflicts)
            score = compute_student_section_score(student_id, section_id, 
                                               student_assignments, scheduled_sections, data)
            if score > 0:
                student_assignments[student_id].append(section_id)
                print(f"Assigned student {student_id} to section {section_id} ({course_id})")
    
    return student_assignments

def format_solution_for_milp(student_assignments, scheduled_sections, data, periods):
    """Format the greedy solution to be used as initial solution for MILP."""
    x_vars = {}  # student-section assignments
    z_vars = {}  # section-period assignments
    y_vars = {}  # student-section-period assignments
    
    # Set z_vars from scheduled_sections
    for section_id, period in scheduled_sections.items():
        z_vars[(section_id, period)] = 1
    
    # Set x_vars from student_assignments
    for student_id, sections in student_assignments.items():
        for section_id in sections:
            x_vars[(student_id, section_id)] = 1
    
    # Set y_vars (derived from x and z)
    for student_id, sections in student_assignments.items():
        for section_id in sections:
            period = scheduled_sections.get(section_id)
            if period:
                y_vars[(student_id, section_id, period)] = 1
    
    return x_vars, z_vars, y_vars

def greedy_initial_solution(students, student_preferences, sections, periods, teacher_unavailability):
    """Generate a feasible initial solution for the MILP using an advanced greedy algorithm."""
    print("Starting improved greedy initial solution generation...")
    
    # Preprocess data
    data = preprocess_data(students, student_preferences, None, sections, teacher_unavailability, periods)
    
    # Schedule sections to periods
    print("Scheduling sections to periods...")
    scheduled_sections = greedy_schedule_sections(sections, periods, data)
    
    section_count = len(scheduled_sections)
    total_sections = len(sections)
    print(f"Scheduled {section_count}/{total_sections} sections ({section_count/total_sections:.1%})")
    
    # Assign students to sections
    print("Assigning students to sections...")
    student_assignments = greedy_assign_students(students, scheduled_sections, data)
    
    # Count satisfied course requests
    total_assignments = sum(len(sections) for sections in student_assignments.values())
    total_requests = sum(len(courses) for courses in data['student_pref_courses'].values())
    print(f"Satisfied {total_assignments}/{total_requests} course requests ({total_assignments/total_requests:.1%})")
    
    # Format solution for MILP
    x_vars, z_vars, y_vars = format_solution_for_milp(student_assignments, scheduled_sections, data, periods)
    
    return x_vars, z_vars, y_vars

def save_solution_to_s3(student_assignments, scheduled_sections, sections_df, 
                      bucket_name, school_id="chico-high-school"):
    """Save solution data to S3 bucket."""
    try:
        s3_client = boto3.client('s3')
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = f"optimization-results/{school_id}/{timestamp}"
        
        # Master schedule
        master_schedule = []
        for section_id, period in scheduled_sections.items():
            master_schedule.append({
                'Section ID': section_id,
                'Period': period
            })
        master_schedule_df = pd.DataFrame(master_schedule)
        master_schedule_bytes = master_schedule_df.to_csv(index=False).encode('utf-8')
        master_schedule_key = f"{output_path}/Master_Schedule.csv"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=master_schedule_key,
            Body=master_schedule_bytes
        )
        
        # Student assignments
        student_assign = []
        for student_id, sections in student_assignments.items():
            for section_id in sections:
                student_assign.append({
                    'Student ID': student_id,
                    'Section ID': section_id
                })
        student_assignments_df = pd.DataFrame(student_assign)
        student_assignments_bytes = student_assignments_df.to_csv(index=False).encode('utf-8')
        student_assignments_key = f"{output_path}/Student_Assignments.csv"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=student_assignments_key,
            Body=student_assignments_bytes
        )
        
        # Teacher schedule - Handle sections_df properly
        if isinstance(sections_df, pd.DataFrame):
            section_to_teacher = sections_df.set_index('Section ID')['Teacher Assigned'].to_dict()
        else:
            # Fallback if sections_df is not a DataFrame
            print("Warning: sections parameter is not a DataFrame, teacher schedules may be incomplete")
            section_to_teacher = {}
            
        teacher_schedule = []
        for section_id, period in scheduled_sections.items():
            teacher_id = section_to_teacher.get(section_id)
            if teacher_id:
                teacher_schedule.append({
                    'Teacher ID': teacher_id,
                    'Section ID': section_id,
                    'Period': period
                })
        teacher_schedule_df = pd.DataFrame(teacher_schedule)
        teacher_schedule_bytes = teacher_schedule_df.to_csv(index=False).encode('utf-8')
        teacher_schedule_key = f"{output_path}/Teacher_Schedule.csv"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=teacher_schedule_key,
            Body=teacher_schedule_bytes
        )
        
        print(f"Results saved to S3 bucket '{bucket_name}' in folder '{output_path}'")
        return {
            'master_schedule': f"s3://{bucket_name}/{master_schedule_key}",
            'student_assignments': f"s3://{bucket_name}/{student_assignments_key}",
            'teacher_schedule': f"s3://{bucket_name}/{teacher_schedule_key}"
        }
        
    except Exception as e:
        print(f"Error saving to S3: {str(e)}")
        raise

def output_results(student_assignments, scheduled_sections, sections_df):
    """Output the greedy solution to CSV files."""
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    # Create Master_Schedule.csv
    master_schedule = []
    for section_id, period in scheduled_sections.items():
        master_schedule.append({
            'Section ID': section_id,
            'Period': period
        })
    pd.DataFrame(master_schedule).to_csv(output_dir / 'Master_Schedule.csv', index=False)
    
    # Create Student_Assignments.csv
    student_assign = []
    for student_id, sections in student_assignments.items():
        for section_id in sections:
            student_assign.append({
                'Student ID': student_id,
                'Section ID': section_id
            })
    pd.DataFrame(student_assign).to_csv(output_dir / 'Student_Assignments.csv', index=False)
    
    # Create Teacher_Schedule.csv - Handle sections_df properly
    if isinstance(sections_df, pd.DataFrame):
        section_to_teacher = sections_df.set_index('Section ID')['Teacher Assigned'].to_dict()
    else:
        # Fallback if sections_df is not a DataFrame
        print("Warning: sections parameter is not a DataFrame, teacher schedules may be incomplete")
        section_to_teacher = {}
        
    teacher_schedule = []
    for section_id, period in scheduled_sections.items():
        teacher_id = section_to_teacher.get(section_id)
        if teacher_id:
            teacher_schedule.append({
                'Teacher ID': teacher_id,
                'Section ID': section_id,
                'Period': period
            })
    pd.DataFrame(teacher_schedule).to_csv(output_dir / 'Teacher_Schedule.csv', index=False)
    
    print(f"Results saved to {output_dir}")

def main():
    """Run the greedy algorithm as a standalone program."""
    # Parse command-line arguments for AWS integration
    parser = argparse.ArgumentParser(description='Run greedy scheduling algorithm')
    parser.add_argument('--use-s3', action='store_true', help='Use S3 for data storage')
    parser.add_argument('--bucket-name', type=str, help='S3 bucket name')
    parser.add_argument('--school-prefix', type=str, help='S3 prefix for school data')
    parser.add_argument('--school-id', type=str, default='chico-high-school', help='School identifier')
    
    args = parser.parse_args()
    
    # If arguments not provided, check environment variables
    use_s3 = args.use_s3 or os.environ.get('USE_S3', 'false').lower() == 'true'
    bucket_name = args.bucket_name or os.environ.get('BUCKET_NAME')
    school_prefix = args.school_prefix or os.environ.get('SCHOOL_PREFIX')
    school_id = args.school_id or os.environ.get('SCHOOL_ID', 'chico-high-school')
    
    print("Starting greedy scheduling algorithm...")
    start_time = time.time()
    
    # Load data with S3 support
    students, student_preferences, teachers, sections, teacher_unavailability, periods = load_data(
        input_dir="input",
        use_s3=use_s3,
        bucket_name=bucket_name,
        school_prefix=school_prefix,
        school_id=school_id
    )
    
    if not isinstance(sections, pd.DataFrame):
        raise TypeError("Sections data must be a pandas DataFrame")
    
    # Run greedy algorithm
    data = preprocess_data(students, student_preferences, teachers, sections, teacher_unavailability, periods)
    scheduled_sections = greedy_schedule_sections(sections, periods, data)
    student_assignments = greedy_assign_students(students, scheduled_sections, data)
    
    # Output results based on storage mode
    if use_s3 and bucket_name:
        save_solution_to_s3(student_assignments, scheduled_sections, sections, bucket_name, school_id)
    else:
        output_results(student_assignments, scheduled_sections, sections)
    
    # Calculate statistics
    section_count = len(scheduled_sections)
    total_sections = len(sections)
    total_assignments = sum(len(sections) for sections in student_assignments.values())
    total_requests = sum(len(courses) for courses in data['student_pref_courses'].values())
    
    print("\nScheduling Statistics:")
    print(f"Scheduled {section_count}/{total_sections} sections ({section_count/total_sections:.1%})")
    print(f"Satisfied {total_assignments}/{total_requests} course requests ({total_assignments/total_requests:.1%})")
    print(f"Total runtime: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()