# Standard library imports
import os
import logging
from datetime import datetime
import platform
import argparse

# Third-party imports
import gurobipy as gp
from gurobipy import GRB
import pandas as pd

# Local imports
from load import ScheduleDataLoader
import greedy  # Import the greedy module

class ScheduleOptimizer:
    def __init__(self, use_s3=False, bucket_name=None, school_prefix=None, school_id=None):
        """Initialize the scheduler using the existing data loader
        
        Args:
            use_s3 (bool): Whether to use S3 for data storage
            bucket_name (str): S3 bucket name if using S3
            school_prefix (str): S3 prefix for school data if using S3
            school_id (str): School identifier if using S3
        """
        # Set up logging
        self.setup_logging()
        
        # Initialize data loader with S3 parameters if provided
        self.use_s3 = use_s3
        self.bucket_name = bucket_name
        self.school_prefix = school_prefix
        self.school_id = school_id
        
        # Use the data loader with appropriate parameters
        loader = ScheduleDataLoader(
            use_s3=self.use_s3, 
            bucket_name=self.bucket_name,
            school_prefix=self.school_prefix,
            school_id=self.school_id
        )
        self.data = loader.load_all()
        
        # Store the loader for later use (e.g., saving solution)
        self.loader = loader
        
        # Extract data from loader
        self.students = self.data['students']
        self.student_preferences = self.data['student_preferences']
        self.teachers = self.data['teachers']
        self.sections = self.data['sections']
        self.teacher_unavailability = self.data['teacher_unavailability']
        
        # Define periods
        self.periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']
        
        # Define course period restrictions once
        self.course_period_restrictions = {
            'Medical Career': ['R1', 'G1'],
            'Heroes Teach': ['R2', 'G2']
        }
        
        # Create course to sections mapping
        self.course_to_sections = {}
        for _, row in self.sections.iterrows():
            if row['Course ID'] not in self.course_to_sections:
                self.course_to_sections[row['Course ID']] = []
            self.course_to_sections[row['Course ID']].append(row['Section ID'])
        
        # Initialize the Gurobi model
        self.model = gp.Model("School_Scheduling")
        
        self.logger.info("Initialization complete")
    
    def get_allowed_periods(self, course_id):
        """Get allowed periods for a course based on restrictions"""
        return self.course_period_restrictions.get(course_id, self.periods)

    def setup_logging(self):
        """Set up logging configuration"""
        output_dir = 'output'
        os.makedirs(output_dir, exist_ok=True)
        
        log_filename = os.path.join(output_dir, f'gurobi_scheduling_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_variables(self):
        """Create decision variables for the model"""
        # x[i,j] = 1 if student i is assigned to section j
        self.x = {}
        for _, student in self.students.iterrows():
            student_id = student['Student ID']
            prefs = self.student_preferences[
                self.student_preferences['Student ID'] == student_id
            ]['Preferred Sections'].iloc[0].split(';')
            
            for course_id in prefs:
                if course_id in self.course_to_sections:
                    for section_id in self.course_to_sections[course_id]:
                        self.x[student_id, section_id] = self.model.addVar(
                            vtype=GRB.BINARY,
                            name=f'x_{student_id}_{section_id}'
                        )

        # z[j,p] = 1 if section j is scheduled in period p
        self.z = {}
        for _, section in self.sections.iterrows():
            section_id = section['Section ID']
            course_id = section['Course ID']
            
            # Use centralized method for period restrictions
            allowed_periods = self.get_allowed_periods(course_id)
                
            for period in allowed_periods:
                self.z[section_id, period] = self.model.addVar(
                    vtype=GRB.BINARY,
                    name=f'z_{section_id}_{period}'
                )

        # y[i,j,p] = 1 if student i is assigned to section j in period p
        self.y = {}
        for (student_id, section_id), x_var in self.x.items():
            for period in self.periods:
                if (section_id, period) in self.z:
                    self.y[student_id, section_id, period] = self.model.addVar(
                        vtype=GRB.BINARY,
                        name=f'y_{student_id}_{section_id}_{period}'
                    )

        # SOFT CONSTRAINT VARIABLES
        # missed_request[i,c] = 1 if student i doesn't get course c they requested
        self.missed_request = {}
        for _, student in self.students.iterrows():
            student_id = student['Student ID']
            prefs = self.student_preferences[
                self.student_preferences['Student ID'] == student_id
            ]['Preferred Sections'].iloc[0].split(';')
            
            for course_id in prefs:
                if course_id in self.course_to_sections:
                    self.missed_request[student_id, course_id] = self.model.addVar(
                        vtype=GRB.BINARY,
                        name=f'missed_{student_id}_{course_id}'
                    )
        
        # capacity_violation[j] = how many students over capacity are assigned to section j
        self.capacity_violation = {}
        for _, section in self.sections.iterrows():
            section_id = section['Section ID']
            self.capacity_violation[section_id] = self.model.addVar(
                vtype=GRB.INTEGER,
                lb=0,
                name=f'capacity_violation_{section_id}'
            )

        self.model.update()
        self.logger.info("Variables created successfully")

    def add_constraints(self):
        """Add all necessary constraints to the model"""
        
        # 1. Each section must be scheduled in exactly one period
        for section_id in self.sections['Section ID']:
            valid_periods = [p for p in self.periods if (section_id, p) in self.z]
            if valid_periods:
                self.model.addConstr(
                    gp.quicksum(self.z[section_id, p] for p in valid_periods) == 1,
                    name=f'one_period_{section_id}'
                )

        # 2. SOFT Section capacity constraints - track violations instead of enforcing hard limit
        for _, section in self.sections.iterrows():
            section_id = section['Section ID']
            capacity = section['# of Seats Available']
            self.model.addConstr(
                gp.quicksum(self.x[student_id, section_id] 
                           for student_id in self.students['Student ID']
                           if (student_id, section_id) in self.x) <= capacity + self.capacity_violation[section_id],
                name=f'soft_capacity_{section_id}'
            )

        # 3. SOFT Student course requirements - using missed_request variables
        for _, student in self.students.iterrows():
            student_id = student['Student ID']
            requested_courses = self.student_preferences[
                self.student_preferences['Student ID'] == student_id
            ]['Preferred Sections'].iloc[0].split(';')
            
            for course_id in requested_courses:
                if course_id in self.course_to_sections:
                    self.model.addConstr(
                        gp.quicksum(self.x[student_id, section_id]
                                  for section_id in self.course_to_sections[course_id]
                                  if (student_id, section_id) in self.x) + 
                        self.missed_request[student_id, course_id] == 1,
                        name=f'soft_course_requirement_{student_id}_{course_id}'
                    )

        # 4. Teacher conflicts - no teacher can teach multiple sections in same period
        for _, teacher in self.teachers.iterrows():
            teacher_id = teacher['Teacher ID']
            teacher_sections = self.sections[
                self.sections['Teacher Assigned'] == teacher_id
            ]['Section ID']
            
            for period in self.periods:
                self.model.addConstr(
                    gp.quicksum(self.z[section_id, period]
                               for section_id in teacher_sections
                               if (section_id, period) in self.z) <= 1,
                    name=f'teacher_conflict_{teacher_id}_{period}'
                )

        # 5. Student period conflicts
        for student_id in self.students['Student ID']:
            for period in self.periods:
                self.model.addConstr(
                    gp.quicksum(self.y[student_id, section_id, period]
                               for section_id in self.sections['Section ID']
                               if (student_id, section_id, period) in self.y) <= 1,
                    name=f'student_period_conflict_{student_id}_{period}'
                )

        # 6. Linking constraints between x, y, and z variables
        for (student_id, section_id, period), y_var in self.y.items():
            self.model.addConstr(
                y_var <= self.x[student_id, section_id],
                name=f'link_xy_{student_id}_{section_id}_{period}'
            )
            self.model.addConstr(
                y_var <= self.z[section_id, period],
                name=f'link_yz_{student_id}_{section_id}_{period}'
            )
            self.model.addConstr(
                y_var >= self.x[student_id, section_id] + self.z[section_id, period] - 1,
                name=f'link_xyz_{student_id}_{section_id}_{period}'
            )

        # 7. SPED student distribution constraint (soft)
        sped_students = self.students[self.students['SPED'] == 1]['Student ID']
        for section_id in self.sections['Section ID']:
            self.model.addConstr(
                gp.quicksum(self.x[student_id, section_id]
                           for student_id in sped_students
                           if (student_id, section_id) in self.x) <= 12,
                name=f'sped_distribution_{section_id}'
            )

        self.logger.info("Constraints added successfully")

    def set_objective(self):
        """Set the objective function to maximize student satisfaction with soft constraints"""
        # Calculate total number of student-course requests for scaling
        total_requests = sum(1 for key in self.missed_request)
        
        # Calculate total section capacity for scaling
        total_capacity = sum(self.sections['# of Seats Available'])
        
        # Primary objective: minimize missed requests (high priority)
        missed_requests_penalty = 1000 * gp.quicksum(self.missed_request[student_id, course_id]
                                              for (student_id, course_id) in self.missed_request)
        
        # Secondary objective: minimize capacity violations (lower priority)
        capacity_penalty = 1 * gp.quicksum(self.capacity_violation[section_id]
                                          for section_id in self.capacity_violation)
        
        # Set objective to minimize penalties (equivalent to maximizing satisfaction)
        self.model.setObjective(missed_requests_penalty + capacity_penalty, GRB.MINIMIZE)
        self.logger.info("Objective function with soft constraints set successfully")

    def greedy_initial_solution(self):
        """Generate a feasible initial solution using the advanced greedy algorithm"""
        self.logger.info("Generating initial solution using advanced greedy algorithm...")
        
        try:
            # Format data for greedy algorithm
            student_data = self.students
            student_pref_data = self.student_preferences
            section_data = self.sections
            periods = self.periods
            teacher_unavailability = self.teacher_unavailability
            
            # Call the greedy algorithm from greedy.py
            x_vars, z_vars, y_vars = greedy.greedy_initial_solution(
                student_data, student_pref_data, section_data, periods, teacher_unavailability
            )
            
            self.logger.info(f"Greedy algorithm generated initial values for: {len(x_vars)} x vars, "
                            f"{len(z_vars)} z vars, {len(y_vars)} y vars")
            
            # Set start values for Gurobi variables
            # Set x variables
            for (student_id, section_id), value in x_vars.items():
                if (student_id, section_id) in self.x:
                    self.x[student_id, section_id].start = value
            
            # Set z variables
            for (section_id, period), value in z_vars.items():
                if (section_id, period) in self.z:
                    self.z[section_id, period].start = value
            
            # Set y variables
            for (student_id, section_id, period), value in y_vars.items():
                if (student_id, section_id, period) in self.y:
                    self.y[student_id, section_id, period].start = value
            
            # Calculate solution quality metrics
            assigned_students = sum(1 for (_, _), val in x_vars.items() if val > 0.5)
            total_students = len(self.students)
            assigned_sections = len(set(section_id for (_, section_id), val in x_vars.items() if val > 0.5))
            total_sections = len(self.sections)
            
            self.logger.info(f"Initial solution: {assigned_students}/{total_students} students assigned, "
                            f"{assigned_sections}/{total_sections} sections used")
            
            # Set the MIPFocus parameter to use the initial solution effectively
            self.model.setParam('MIPFocus', 1)  # Focus on finding good feasible solutions
            
        except Exception as e:
            self.logger.error(f"Error generating initial solution: {str(e)}")
            self.logger.warning("Falling back to simple greedy algorithm")
            self._simple_greedy_initial_solution()
        
    def _simple_greedy_initial_solution(self):
        """Original simple greedy algorithm as fallback"""
        # Initialize capacity tracking
        section_capacity = self.sections.set_index('Section ID')['# of Seats Available'].to_dict()
        
        # Initialize assignments
        student_assignments = {}
        section_periods = {}
        
        # Assign students to sections based on preferences
        for _, student in self.students.iterrows():
            student_id = student['Student ID']
            prefs = self.student_preferences[
                self.student_preferences['Student ID'] == student_id
            ]['Preferred Sections'].iloc[0].split(';')
            
            for course_id in prefs:
                if (course_id in self.course_to_sections) and (student_id not in student_assignments):
                    for section_id in self.course_to_sections[course_id]:
                        if section_capacity[section_id] > 0:
                            student_assignments[student_id] = section_id
                            section_capacity[section_id] -= 1
                            break
        
        # Assign sections to periods
        for _, section in self.sections.iterrows():
            section_id = section['Section ID']
            course_id = section['Course ID']
            
            # Use centralized method for period restrictions
            allowed_periods = self.get_allowed_periods(course_id)
            
            for period in allowed_periods:
                if (section_id, period) in self.z:
                    section_periods[section_id] = period
                    break
        
        # Set start values for decision variables
        for (student_id, section_id), x_var in self.x.items():
            if student_assignments.get(student_id) == section_id:
                x_var.start = 1
            else:
                x_var.start = 0
        
        for (section_id, period), z_var in self.z.items():
            if section_periods.get(section_id) == period:
                z_var.start = 1
            else:
                z_var.start = 0
        
        for (student_id, section_id, period), y_var in self.y.items():
            if student_assignments.get(student_id) == section_id and section_periods.get(section_id) == period:
                y_var.start = 1
            else:
                y_var.start = 0
        
        self.logger.info("Simple greedy initial solution generated successfully")

    def solve(self):
        """Solve the optimization model to find a solution in the top 10%"""
        try:
            # Calculate upper bound on objective (total course requests)
            total_requests = 0
            for _, student in self.students.iterrows():
                student_id = student['Student ID']
                requested_courses = self.student_preferences[
                    self.student_preferences['Student ID'] == student_id
                ]['Preferred Sections'].iloc[0].split(';')
                total_requests += len(requested_courses)
            
            # Get system memory information
            import psutil
            total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)  # RAM in GB
            
            # Use 95% of available RAM as requested
            mem_limit_gb = int(total_ram_gb * 0.95)
            node_file_start = 0.95  # Start writing to disk at 95% memory usage
            
            self.logger.info("=" * 80)
            self.logger.info(f"SYSTEM CONFIGURATION")
            self.logger.info(f"System has {total_ram_gb:.1f} GB of RAM available")
            self.logger.info(f"Setting Gurobi memory limit to {mem_limit_gb} GB (95% of available RAM)")
            
            # Set memory limit - convert GB to MB
            self.model.setParam('MemLimit', mem_limit_gb * 1024)
            
            # Set parameters as requested
            self.model.setParam('Presolve', 1)  # Use standard presolve
            self.model.setParam('Method', 1)    # Use dual simplex for LP relaxations
            self.model.setParam('MIPFocus', 1)  # Focus on feasible solutions
            
            # Other parameters
            self.model.setParam('MIPGap', 0.10)     # 10% MIP gap tolerance
            self.model.setParam('TimeLimit', 25200)  # 7 hours time limit
            
            # Set up node file storage
            self.model.setParam('NodefileStart', node_file_start)
            
            # Set the directory for node file offloading
            if platform.system() == 'Windows':
                node_dir = 'c:/temp/gurobi_nodefiles'
            else:
                node_dir = '/tmp/gurobi_nodefiles'
                
            os.makedirs(node_dir, exist_ok=True)
            self.model.setParam('NodefileDir', node_dir)
            self.logger.info(f"Node file directory: {node_dir}")
            self.logger.info(f"Will switch to disk storage when memory reaches {node_file_start*100}% of allocated RAM")
            
            # Set verbosity level for detailed console output
            self.model.setParam('OutputFlag', 1)     # Enable Gurobi output
            self.model.setParam('DisplayInterval', 5) # Show log lines every 5 seconds
            
            # Determine optimal number of threads based on system
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            threads = min(cpu_count - 1, 32)  # Leave 1 core free, cap at 32 threads
            self.model.setParam('Threads', threads)
            self.logger.info(f"Using {threads} threads out of {cpu_count} available cores")
            
            # Add callback to monitor disk usage - with proper error handling
            def node_file_callback(model, where):
                if where == GRB.Callback.MIP:
                    try:
                        nodefile = model.cbGet(GRB.Callback.MIP_NODEFILE)
                        if nodefile > 0 and not hasattr(model, '_reported_disk_usage'):
                            self.logger.warning(f"SWITCHED TO DISK STORAGE: Now using {nodefile:.2f} MB of disk space for node storage")
                            model._reported_disk_usage = True
                    except (AttributeError, TypeError):
                        # Silently handle the case where MIP_NODEFILE isn't available
                        pass
            
            # Generate a greedy initial solution
            self.greedy_initial_solution()
            
            self.logger.info("=" * 80)
            self.logger.info("STARTING OPTIMIZATION")
            self.logger.info(f"Maximum possible satisfied requests: {total_requests}")
            self.logger.info("=" * 80)
            
            # Optimize with callback
            self.model.optimize(node_file_callback)
            
            self.logger.info("=" * 80)
            self.logger.info("OPTIMIZATION RESULTS")
            
            if self.model.status == GRB.OPTIMAL or (self.model.status == GRB.TIME_LIMIT and self.model.SolCount > 0):
                # Calculate the actual satisfaction metrics from variables, not objective value
                missed_count = sum(var.X > 0.5 for var in self.missed_request.values())
                satisfied_requests = total_requests - missed_count
                satisfaction_rate = (satisfied_requests / total_requests) * 100
                
                if self.model.status == GRB.OPTIMAL:
                    self.logger.info("STATUS: Found optimal solution!")
                else:
                    self.logger.info("STATUS: Time limit reached but found good solution")
                    
                self.logger.info(f"SATISFIED REQUESTS: {satisfied_requests} out of {total_requests}")
                self.logger.info(f"SATISFACTION RATE: {satisfaction_rate:.2f}%")
                
                # Calculate capacity violation metrics
                sections_over_capacity = sum(1 for var in self.capacity_violation.values() if var.X > 0.5)
                total_violations = sum(var.X for var in self.capacity_violation.values())
                self.logger.info(f"CAPACITY VIOLATIONS: {sections_over_capacity} sections over capacity")
                self.logger.info(f"TOTAL OVERAGES: {int(total_violations)} students over capacity")
                
                # Weighted objective breakdown
                missed_requests_penalty = 1000 * missed_count
                capacity_penalty = sum(var.X for var in self.capacity_violation.values())
                self.logger.info(f"OBJECTIVE VALUE: {self.model.objVal}")
                self.logger.info(f"  - Missed requests penalty: {missed_requests_penalty}")
                self.logger.info(f"  - Capacity violations penalty: {capacity_penalty}")
                
                # Runtime statistics
                self.logger.info(f"RUNTIME: {self.model.Runtime:.2f} seconds")
                self.logger.info(f"NODES EXPLORED: {self.model.NodeCount}")
                self.logger.info(f"MIP GAP: {self.model.MIPGap*100:.2f}%")
                
                # Peak memory usage - with error handling
                try:
                    # Try to get peak memory usage, but don't crash if not available
                    if hasattr(self.model, 'NodeFileStart'):
                        peak_mem = self.model.getAttr('NodeFileStart') * mem_limit_gb * 1024  # MB
                        self.logger.info(f"PEAK MEMORY USAGE: {peak_mem:.2f} MB")
                    else:
                        self.logger.info("PEAK MEMORY USAGE: Not available")
                except Exception as e:
                    self.logger.warning(f"Cannot retrieve peak memory usage: {str(e)}")
                
                self.logger.info("=" * 80)
                self.logger.info("Saving solution files...")
                self.save_solution()
            elif self.model.status == GRB.TIME_LIMIT:
                self.logger.error("STATUS: Time limit reached without finding any solution")
            else:
                self.logger.error(f"STATUS: Optimization failed with status code {self.model.status}")
                
        except gp.GurobiError as e:
            self.logger.error(f"GUROBI ERROR: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"UNEXPECTED ERROR: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            # Try to save any solution that might exist despite the error
            if hasattr(self.model, 'SolCount') and self.model.SolCount > 0:
                self.logger.info("Attempting to save partial solution despite error...")
                try:
                    self.save_solution()
                except Exception as save_error:
                    self.logger.error(f"Failed to save solution: {str(save_error)}")
            raise

    def save_solution(self):
        """Save the solution to CSV files using the data loader's save method"""
        # Extract section schedule
        section_schedule = []
        for (section_id, period), z_var in self.z.items():
            if z_var.X > 0.5:
                section_schedule.append({
                    'Section ID': section_id,
                    'Period': period
                })

        # Extract student assignments
        student_assignments = []
        for (student_id, section_id), x_var in self.x.items():
            if x_var.X > 0.5:
                student_assignments.append({
                    'Student ID': student_id,
                    'Section ID': section_id
                })

        # Extract teacher schedule
        teacher_schedule = []
        for (section_id, period), z_var in self.z.items():
            if z_var.X > 0.5:
                teacher_id = self.sections[
                    self.sections['Section ID'] == section_id
                ]['Teacher Assigned'].iloc[0]
                teacher_schedule.append({
                    'Teacher ID': teacher_id,
                    'Section ID': section_id,
                    'Period': period
                })

        # Calculate metrics for soft constraints
        constraint_violations = []
        
        # Calculate and save missed requests
        missed_count = sum(var.X > 0.5 for var in self.missed_request.values())
        total_requests = len(self.missed_request)
        constraint_violations.append({
            'Metric': 'Missed Requests',
            'Count': int(missed_count),
            'Total': total_requests,
            'Percentage': f"{100 * missed_count / total_requests:.2f}%"
        })
        
        # Calculate and save capacity violations
        sections_over_capacity = sum(1 for var in self.capacity_violation.values() if var.X > 0.5)
        total_violations = sum(var.X for var in self.capacity_violation.values())
        constraint_violations.append({
            'Metric': 'Sections Over Capacity',
            'Count': int(sections_over_capacity),
            'Total Sections': len(self.sections),
            'Total Overages': int(total_violations)
        })
        
        # Use the data loader's save_solution method to save to local filesystem or S3
        result_locations = self.loader.save_solution(
            section_schedule, 
            student_assignments,
            teacher_schedule,
            constraint_violations
        )
        
        # Log the file locations
        self.logger.info("Solution saved successfully")
        for file_type, location in result_locations.items():
            self.logger.info(f"  - {file_type}: {location}")

if __name__ == "__main__":
    try:
        # Parse command-line arguments for AWS integration
        parser = argparse.ArgumentParser(description='Run school schedule optimization')
        parser.add_argument('--use-s3', action='store_true', help='Use S3 for data storage')
        parser.add_argument('--bucket-name', type=str, help='S3 bucket name')
        parser.add_argument('--school-prefix', type=str, help='S3 prefix for school data')
        parser.add_argument('--school-id', type=str, help='School identifier')
        
        args = parser.parse_args()
        
        # If arguments not provided, check environment variables
        use_s3 = args.use_s3 or os.environ.get('USE_S3', 'false').lower() == 'true'
        bucket_name = args.bucket_name or os.environ.get('BUCKET_NAME')
        school_prefix = args.school_prefix or os.environ.get('SCHOOL_PREFIX')
        school_id = args.school_id or os.environ.get('SCHOOL_ID')
        
        # Initialize optimizer with AWS parameters if provided
        optimizer = ScheduleOptimizer(
            use_s3=use_s3,
            bucket_name=bucket_name,
            school_prefix=school_prefix,
            school_id=school_id
        )
        
        # Run the optimization process
        optimizer.create_variables()
        optimizer.add_constraints()
        optimizer.set_objective()
        optimizer.solve()
        
    except KeyboardInterrupt:
        logging.info("Optimization interrupted by user")
    except Exception as e:
        logging.error(f"Error running optimization: {str(e)}")
        raise