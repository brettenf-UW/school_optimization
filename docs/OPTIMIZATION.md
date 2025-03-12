# Optimization Process Documentation

## Overview

The Echelon platform uses a two-stage optimization approach to create optimal school master schedules:

1. **Greedy Algorithm** (in `greedy.py`): Creates a feasible initial solution
2. **Mixed Integer Linear Programming** (in `milp_soft.py`): Refines the solution to optimality

## Data Requirements

The optimization requires the following data files:

- **students.csv**: Student information
- **teachers.csv**: Teacher information
- **sections.csv**: Section/course information
- **preferences.csv**: Student course preferences
- **unavailability.csv** (optional): Teacher period unavailability

## Constraints

The optimization handles several types of constraints:

### Hard Constraints
- Teachers cannot teach multiple sections during the same period
- Students cannot be assigned to multiple sections during the same period
- Each section must be scheduled to exactly one period
- Some courses can only be taught during specific periods

### Soft Constraints (Weighted)
- Try to satisfy all student course requests
- Try to keep sections within capacity limits
- Distribute SPED students evenly across sections

## Objective Function

The optimization prioritizes:
1. Maximizing the number of satisfied student course requests
2. Minimizing capacity violations

## Running the Optimization

### Using the API

The most common way to run the optimization is through the web interface, which schedules jobs via the API.

### Direct Command Line

For testing or specialized runs, you can use the command line:

```bash
# Run with local files
python milp_soft.py

# Run with S3 integration
python milp_soft.py --use-s3 --bucket-name my-school-data --school-id chico-high-school
```

### Environment Variables

You can also configure the optimization using environment variables:

```bash
export USE_S3=true
export BUCKET_NAME=chico-high-school-optimization
export SCHOOL_PREFIX=input-data
export SCHOOL_ID=chico-high-school
python milp_soft.py
```

## Performance Considerations

- The optimization is computationally intensive
- For large schools, it can take several hours to reach optimality
- The system uses AWS Batch to provide high-performance computing resources
- Default configuration uses r5.12xlarge instances (48 vCPUs, 384GB RAM)

## Output Files

The optimization produces several output files:

- **Master_Schedule.csv**: Section-to-period assignments
- **Student_Assignments.csv**: Student-to-section assignments
- **Teacher_Schedule.csv**: Teacher schedules
- **Constraint_Violations.csv**: Details about violated soft constraints