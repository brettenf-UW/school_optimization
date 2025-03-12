import pandas as pd
from pathlib import Path
import os
import datetime
import io
import boto3
import logging

class ScheduleDataLoader:
    MAX_LOG_ENTRIES = 100  # Limit logs for large datasets

    def __init__(self, use_s3=False, bucket_name=None, school_prefix=None, school_id=None):
        """Initialize file paths and debug logging.
        
        Args:
            use_s3 (bool): Whether to use S3 for data storage
            bucket_name (str): S3 bucket name if using S3
            school_prefix (str): S3 prefix for school data if using S3
            school_id (str): School identifier if using S3
        """
        self.use_s3 = use_s3
        self.bucket_name = bucket_name
        self.school_prefix = school_prefix or 'input-data'
        self.school_id = school_id or 'chico-high-school'
        
        # Configure paths based on S3 or local storage
        if self.use_s3:
            self.s3_client = boto3.client('s3')
            # Set up S3 paths
            self.input_path = f"{self.school_prefix}/{self.school_id}"
            self.output_path = f"optimization-results/{self.school_id}"
            self.debug_path = f"debug-logs/{self.school_id}"
            
            # Set up logging to both S3 and local
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            
            # Create timestamp for log files
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.summary_key = f"{self.debug_path}/debug_summary_{timestamp}.log"
            self.base_data_key = f"{self.debug_path}/base_data_{timestamp}.log"
            self.relationship_key = f"{self.debug_path}/relationship_data_{timestamp}.log"
            self.validation_key = f"{self.debug_path}/validation_{timestamp}.log"
            
            # Initialize log buffers
            self.summary_buffer = io.StringIO()
            self.base_data_buffer = io.StringIO()
            self.relationship_buffer = io.StringIO() 
            self.validation_buffer = io.StringIO()
            
            self.logger.info(f"[INIT] Using S3 bucket '{bucket_name}' with prefix '{self.input_path}'")
        else:
            # Default to local file paths
            self.project_root = Path(__file__).parent.parent
            self.input_dir = self.project_root / 'input'
            self.debug_dir = self.project_root / 'debug'
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            
            # Create timestamped debug files
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.summary_file = self.debug_dir / f"debug_summary_{timestamp}.log"
            self.base_data_file = self.debug_dir / f"base_data_{timestamp}.log"
            self.relationship_file = self.debug_dir / f"relationship_data_{timestamp}.log"
            self.validation_file = self.debug_dir / f"validation_{timestamp}.log"
            
            if not self.input_dir.exists():
                self.log_summary("[ERROR] Input directory not found.")
                raise FileNotFoundError(f"[ERROR] Input directory not found at {self.input_dir}")

        self.data = {}
        self.log_summary("[INIT] ✅ Data loader initialized successfully.")

    def log(self, file_or_key, message):
        """Write debug logs to the specified log file or S3 object."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        if self.use_s3:
            # For S3, we accumulate logs in buffers and upload at the end
            if file_or_key == self.summary_key:
                self.summary_buffer.write(log_line)
            elif file_or_key == self.base_data_key:
                self.base_data_buffer.write(log_line)
            elif file_or_key == self.relationship_key:
                self.relationship_buffer.write(log_line)
            elif file_or_key == self.validation_key:
                self.validation_buffer.write(log_line)
        else:
            # For local files, write directly
            with open(file_or_key, 'a', encoding='utf-8') as f:
                f.write(log_line)

    def log_summary(self, message):
        """Write to the summary file/object and console."""
        if self.use_s3:
            self.log(self.summary_key, message)
            self.logger.info(message)  # Log to console via logger
        else:
            self.log(self.summary_file, message)
            print(message)  # Also print to console

    def flush_logs_to_s3(self):
        """Upload accumulated logs to S3."""
        if not self.use_s3:
            return
            
        # Upload summary logs
        self.summary_buffer.seek(0)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.summary_key,
            Body=self.summary_buffer.read()
        )
        
        # Upload base data logs
        self.base_data_buffer.seek(0)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.base_data_key,
            Body=self.base_data_buffer.read()
        )
        
        # Upload relationship logs
        self.relationship_buffer.seek(0)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.relationship_key,
            Body=self.relationship_buffer.read()
        )
        
        # Upload validation logs
        self.validation_buffer.seek(0)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.validation_key,
            Body=self.validation_buffer.read()
        )
        
        self.logger.info(f"[LOG] All logs flushed to S3 bucket '{self.bucket_name}'")

    def read_csv_file(self, file_path_or_key):
        """Read a CSV file from local filesystem or S3."""
        if self.use_s3:
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path_or_key)
                content = response['Body'].read()
                return pd.read_csv(io.BytesIO(content))
            except self.s3_client.exceptions.NoSuchKey:
                raise FileNotFoundError(f"[ERROR] File not found in S3: {file_path_or_key}")
            except Exception as e:
                raise Exception(f"[ERROR] Failed to read from S3: {str(e)}")
        else:
            return pd.read_csv(file_path_or_key)

    def load_base_data(self):
        """Load primary data files."""
        try:
            self.log(self.base_data_key if self.use_s3 else self.base_data_file, 
                     "[LOAD] 📦 Loading base data files...")
            
            # Define file paths based on storage type
            if self.use_s3:
                students_path = f"{self.input_path}/students/Student_Info.csv"
                teachers_path = f"{self.input_path}/teachers/Teacher_Info.csv"
                sections_path = f"{self.input_path}/sections/Sections_Information.csv"
                periods_path = f"{self.input_path}/schedule/Period.csv"
            else:
                students_path = self.input_dir / 'Student_Info.csv'
                teachers_path = self.input_dir / 'Teacher_Info.csv'
                sections_path = self.input_dir / 'Sections_Information.csv'
                periods_path = self.input_dir / 'Period.csv'
            
            # Load the files
            self.data['students'] = self.read_csv_file(students_path)
            self.log(self.base_data_key if self.use_s3 else self.base_data_file, 
                     f"[LOAD] ✅ Students loaded: {len(self.data['students'])} records")

            self.data['teachers'] = self.read_csv_file(teachers_path)
            self.log(self.base_data_key if self.use_s3 else self.base_data_file, 
                     f"[LOAD] ✅ Teachers loaded: {len(self.data['teachers'])} records")

            self.data['sections'] = self.read_csv_file(sections_path)
            self.log(self.base_data_key if self.use_s3 else self.base_data_file, 
                     f"[LOAD] ✅ Sections loaded: {len(self.data['sections'])} records")

            self.data['periods'] = self.read_csv_file(periods_path)
            self.log(self.base_data_key if self.use_s3 else self.base_data_file, 
                     f"[LOAD] ✅ Periods loaded: {len(self.data['periods'])} records")

        except FileNotFoundError as e:
            self.log_summary(f"[ERROR] Missing input file: {str(e)}")
            raise
        except Exception as e:
            self.log_summary(f"[ERROR] Failed to load base data: {str(e)}")
            raise

    def load_relationship_data(self):
        """Load relationship data."""
        try:
            self.log(self.relationship_key if self.use_s3 else self.relationship_file, 
                     "[LOAD] 📦 Loading relationship data...")
            
            # Define file paths based on storage type
            if self.use_s3:
                preferences_path = f"{self.input_path}/students/Student_Preference_Info.csv"
                unavailability_path = f"{self.input_path}/teachers/Teacher_unavailability.csv"
            else:
                preferences_path = self.input_dir / 'Student_Preference_Info.csv'
                unavailability_path = self.input_dir / 'Teacher_unavailability.csv'
            
            # Load student preferences
            self.data['student_preferences'] = self.read_csv_file(preferences_path)
            self.log(self.relationship_key if self.use_s3 else self.relationship_file, 
                     f"[LOAD] ✅ Student preferences: {len(self.data['student_preferences'])} records")

            # Load teacher unavailability with error handling
            try:
                self.data['teacher_unavailability'] = self.read_csv_file(unavailability_path)
                self.log(self.relationship_key if self.use_s3 else self.relationship_file, 
                         f"[LOAD] ✅ Teacher unavailability: {len(self.data['teacher_unavailability'])} records")
            except (pd.errors.EmptyDataError, FileNotFoundError):
                self.data['teacher_unavailability'] = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
                self.log(self.relationship_key if self.use_s3 else self.relationship_file, 
                         "[WARNING] ⚠️ Teacher unavailability not found or empty.")

        except FileNotFoundError as e:
            self.log_summary(f"[ERROR] Missing relationship file: {str(e)}")
            raise
        except Exception as e:
            self.log_summary(f"[ERROR] Failed to load relationship data: {str(e)}")
            raise

    def validate_relationships(self):
        """Validate relationships between data."""
        validation_log = self.validation_key if self.use_s3 else self.validation_file
        self.log(validation_log, "[VALIDATE] 🔎 Validating data relationships...")
        validation_issues = []

        sections = self.data['sections']
        teachers = self.data['teachers']
        prefs = self.data['student_preferences']

        # Validate teachers
        teachers_in_sections = sections['Teacher Assigned'].unique()
        known_teachers = teachers['Teacher ID'].unique()
        unknown_teachers = set(teachers_in_sections) - set(known_teachers)
        if unknown_teachers:
            issue = f"[VALIDATE] ⚠️ Unknown teachers: {unknown_teachers}"
            validation_issues.append(issue)
            self.log(validation_log, issue)

        # Validate student preferences
        all_courses = sections['Course ID'].unique()
        for idx, row in prefs.head(self.MAX_LOG_ENTRIES).iterrows():
            requested_courses = str(row['Preferred Sections']).split(';')
            unknown_courses = set(requested_courses) - set(all_courses)
            if unknown_courses:
                issue = f"[VALIDATE] ⚠️ Student {row['Student ID']} references unknown courses: {unknown_courses}"
                validation_issues.append(issue)
                self.log(validation_log, issue)

        if not validation_issues:
            self.log_summary("[VALIDATE] ✅ All relationships are valid.")
        else:
            self.log_summary("[VALIDATE] ❌ Validation issues found. See logs for details.")

    def save_solution(self, section_schedule, student_assignments, teacher_schedule, constraint_violations):
        """Save solution data to local filesystem or S3."""
        try:
            if self.use_s3:
                # Save to S3
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Master schedule
                master_schedule_df = pd.DataFrame(section_schedule)
                master_schedule_bytes = master_schedule_df.to_csv(index=False).encode('utf-8')
                master_schedule_key = f"{self.output_path}/{timestamp}/Master_Schedule.csv"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=master_schedule_key,
                    Body=master_schedule_bytes
                )
                
                # Student assignments
                student_assignments_df = pd.DataFrame(student_assignments)
                student_assignments_bytes = student_assignments_df.to_csv(index=False).encode('utf-8')
                student_assignments_key = f"{self.output_path}/{timestamp}/Student_Assignments.csv"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=student_assignments_key,
                    Body=student_assignments_bytes
                )
                
                # Teacher schedule
                teacher_schedule_df = pd.DataFrame(teacher_schedule)
                teacher_schedule_bytes = teacher_schedule_df.to_csv(index=False).encode('utf-8')
                teacher_schedule_key = f"{self.output_path}/{timestamp}/Teacher_Schedule.csv"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=teacher_schedule_key,
                    Body=teacher_schedule_bytes
                )
                
                # Constraint violations
                violations_df = pd.DataFrame(constraint_violations)
                violations_bytes = violations_df.to_csv(index=False).encode('utf-8')
                violations_key = f"{self.output_path}/{timestamp}/Constraint_Violations.csv"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=violations_key,
                    Body=violations_bytes
                )
                
                self.log_summary(f"[SAVE] ✅ Solution saved to S3 bucket '{self.bucket_name}' in folder '{self.output_path}/{timestamp}'")
                
                # Return file locations for downstream processing
                return {
                    'master_schedule': f"s3://{self.bucket_name}/{master_schedule_key}",
                    'student_assignments': f"s3://{self.bucket_name}/{student_assignments_key}",
                    'teacher_schedule': f"s3://{self.bucket_name}/{teacher_schedule_key}",
                    'constraint_violations': f"s3://{self.bucket_name}/{violations_key}"
                }
                
            else:
                # Save to local filesystem
                output_dir = 'output'
                os.makedirs(output_dir, exist_ok=True)
                
                pd.DataFrame(section_schedule).to_csv(
                    os.path.join(output_dir, 'Master_Schedule.csv'),
                    index=False
                )
                
                pd.DataFrame(student_assignments).to_csv(
                    os.path.join(output_dir, 'Student_Assignments.csv'),
                    index=False
                )
                
                pd.DataFrame(teacher_schedule).to_csv(
                    os.path.join(output_dir, 'Teacher_Schedule.csv'),
                    index=False
                )
                
                pd.DataFrame(constraint_violations).to_csv(
                    os.path.join(output_dir, 'Constraint_Violations.csv'),
                    index=False
                )
                
                self.log_summary(f"[SAVE] ✅ Solution saved to local directory '{output_dir}'")
                
                # Return file locations for downstream processing
                return {
                    'master_schedule': os.path.join(output_dir, 'Master_Schedule.csv'),
                    'student_assignments': os.path.join(output_dir, 'Student_Assignments.csv'),
                    'teacher_schedule': os.path.join(output_dir, 'Teacher_Schedule.csv'),
                    'constraint_violations': os.path.join(output_dir, 'Constraint_Violations.csv')
                }
                
        except Exception as e:
            self.log_summary(f"[ERROR] Failed to save solution: {str(e)}")
            raise

    def load_all(self):
        """Load and validate all data."""
        try:
            self.log_summary("[LOAD ALL] 🚀 Starting data load...")
            self.load_base_data()
            self.load_relationship_data()
            self.validate_relationships()
            
            # Flush logs to S3 if using S3
            if self.use_s3:
                self.flush_logs_to_s3()
                
            self.log_summary("[LOAD ALL] ✅ Data load complete.")
            return self.data
        except Exception as e:
            self.log_summary(f"[ERROR] ❌ An error occurred: {str(e)}")
            if self.use_s3:
                self.logger.error(f"[ERROR] ❌ An error occurred: {str(e)}")
                # Try to flush logs even on error
                try:
                    self.flush_logs_to_s3()
                except:
                    pass
            else:
                print(f"\n[ERROR] ❌ An error occurred: {str(e)}")
            raise


if __name__ == "__main__":
    try:
        # Can test with either local or S3 mode
        use_s3 = os.environ.get('USE_S3', 'false').lower() == 'true'
        bucket_name = os.environ.get('BUCKET_NAME', 'chico-high-school-optimization')
        school_prefix = os.environ.get('SCHOOL_PREFIX', 'input-data')
        school_id = os.environ.get('SCHOOL_ID', 'chico-high-school')
        
        loader = ScheduleDataLoader(use_s3=use_s3, bucket_name=bucket_name, 
                                   school_prefix=school_prefix, school_id=school_id)
        data = loader.load_all()
        print("\n[INFO] Data loaded successfully:")
        for key, df in data.items():
            print(f" - {key}: {len(df)} records")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")