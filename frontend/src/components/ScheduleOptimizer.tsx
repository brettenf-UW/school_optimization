import React, { useState, useEffect } from 'react';
import { Storage, API } from 'aws-amplify';
import { 
  Button, 
  Container, 
  Grid, 
  Box, 
  Typography, 
  LinearProgress,
  Alert,
  AlertTitle,
  Paper,
  Snackbar
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import FileUpload from './FileUpload';

interface FileState {
  studentInfo: File | null;
  studentPreferences: File | null;
  teacherInfo: File | null;
  teacherUnavailability: File | null;
  sectionsInfo: File | null;
  periods: File | null;
}

interface UploadProgress {
  [key: string]: number;
}

interface JobStatus {
  id: string;
  status: string;
  message: string;
  results?: any;
}

interface ScheduleOptimizerProps {
  schoolId?: string;
}

const ScheduleOptimizer: React.FC<ScheduleOptimizerProps> = ({ schoolId = 'chico-high-school' }) => {
  // Track file upload status
  const [files, setFiles] = useState<FileState>({
    studentInfo: null,
    studentPreferences: null,
    teacherInfo: null,
    teacherUnavailability: null,
    sectionsInfo: null,
    periods: null,
  });
  
  // Track upload progress and job status
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({});
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  // File metadata for display
  const fileMetadata = {
    studentInfo: {
      label: "Student Information",
      help: "CSV file containing student records with ID, grade level, and special education status",
      required: true,
      path: 'students/Student_Info.csv'
    },
    studentPreferences: {
      label: "Student Course Preferences",
      help: "CSV file with student course requests and preference rankings",
      required: true,
      path: 'students/Student_Preference_Info.csv'
    },
    teacherInfo: {
      label: "Teacher Information",
      help: "CSV file with teacher records including ID and other attributes",
      required: true,
      path: 'teachers/Teacher_Info.csv'
    },
    teacherUnavailability: {
      label: "Teacher Unavailability",
      help: "CSV file indicating which periods teachers cannot teach",
      required: false,
      path: 'teachers/Teacher_unavailability.csv'
    },
    sectionsInfo: {
      label: "Sections Information",
      help: "CSV file with course sections, capacities, and teacher assignments",
      required: true,
      path: 'sections/Sections_Information.csv'
    },
    periods: {
      label: "School Periods",
      help: "CSV file defining the school schedule periods",
      required: true,
      path: 'schedule/Period.csv'
    }
  };
  
  // Check if all required files are uploaded
  const allRequiredFilesUploaded = () => {
    return Object.entries(fileMetadata)
      .filter(([_, metadata]) => metadata.required)
      .every(([fileType]) => files[fileType as keyof FileState] !== null);
  };
  
  // Handle file selection
  const handleFileSelect = (fileType: keyof FileState, file: File | null) => {
    setFiles({
      ...files,
      [fileType]: file
    });
  };
  
  // Upload a single file to S3
  const uploadFile = async (fileType: keyof FileState, file: File) => {
    const s3Path = `input-data/${schoolId}/${fileMetadata[fileType].path}`;
    
    try {
      await Storage.put(s3Path, file, {
        contentType: 'text/csv',
        progressCallback: (progress) => {
          setUploadProgress({
            ...uploadProgress,
            [fileType]: (progress.loaded / progress.total) * 100
          });
        }
      });
      return true;
    } catch (err: any) {
      console.error(`Error uploading ${fileType}:`, err);
      setError(`Failed to upload ${fileType}: ${err.message}`);
      return false;
    }
  };
  
  // Upload all files
  const uploadAllFiles = async () => {
    setUploading(true);
    setError(null);
    
    try {
      const uploadPromises = Object.entries(files)
        .filter(([fileType, file]) => file !== null)
        .map(([fileType, file]) => {
          return uploadFile(fileType as keyof FileState, file as File);
        });
      
      const results = await Promise.all(uploadPromises);
      const allSuccessful = results.every(result => result);
      
      if (allSuccessful) {
        setSuccessMessage('All files uploaded successfully!');
        setUploadProgress({});
        return true;
      } else {
        throw new Error('Some files failed to upload');
      }
    } catch (err: any) {
      setError(`Upload failed: ${err.message}`);
      return false;
    } finally {
      setUploading(false);
    }
  };
  
  // Start optimization job
  const startOptimizationJob = async () => {
    try {
      // First upload all files
      const uploadSuccess = await uploadAllFiles();
      if (!uploadSuccess) return;
      
      // Check if we're in development mode (localhost)
      // Force production mode for testing AWS Batch integration
      const isDevelopment = false; // window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      
      if (isDevelopment) {
        // Simulate job submission for local development
        console.log('Development mode: Simulating job submission');
        
        // Create a simulated job ID
        const mockJobId = `dev-job-${Date.now()}`;
        
        setJobStatus({
          id: mockJobId,
          status: 'SUBMITTED',
          message: 'Optimization job submitted successfully! (Development Mode)'
        });
        
        setSuccessMessage('Development Mode: Optimization job started! (This is a simulation)');
        
        // Simulate job status changes
        setTimeout(() => {
          setJobStatus({
            id: mockJobId,
            status: 'RUNNING',
            message: 'Optimization is in progress (Development Mode)'
          });
        }, 3000);
        
        setTimeout(() => {
          setJobStatus({
            id: mockJobId,
            status: 'SUCCEEDED',
            message: 'Optimization completed successfully! (Development Mode)',
            results: [
              { name: 'Master_Schedule.csv', url: '#' },
              { name: 'Student_Assignments.csv', url: '#' },
              { name: 'Teacher_Schedule.csv', url: '#' }
            ]
          });
          setSuccessMessage('Development Mode: Optimization completed! Results would be available in production.');
        }, 10000);
        
      } else {
        // Production mode - call actual API
        try {
          const response = await API.post('optimizationApi', '/jobs', {
            body: {
              schoolId: schoolId,
              optimizationType: 'milp_soft'
            }
          });
          
          setJobStatus({
            id: response.jobId,
            status: 'SUBMITTED',
            message: 'Optimization job submitted successfully!'
          });
          
          setSuccessMessage('Optimization job started! This may take several hours to complete.');
          
          // Start polling for job status
          startJobStatusPolling(response.jobId);
        } catch (apiError: any) {
          console.error('API error:', apiError);
          setError(`Failed to communicate with optimization API: ${apiError.message || 'Unknown error'}`);
        }
      }
    } catch (err: any) {
      setError(`Failed to start optimization: ${err.message}`);
    }
  };
  
  // Poll for job status
  const startJobStatusPolling = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await API.get('optimizationApi', `/jobs/${jobId}/status`);
        setJobStatus(status);
        
        // Stop polling when job is complete
        if (['SUCCEEDED', 'FAILED'].includes(status.status)) {
          clearInterval(interval);
          
          if (status.status === 'SUCCEEDED') {
            setSuccessMessage('Optimization completed successfully! You can now view the results.');
          } else {
            setError(`Optimization failed: ${status.message}`);
          }
        }
      } catch (err: any) {
        console.error('Error polling job status:', err);
      }
    }, 30000); // Poll every 30 seconds
    
    // Clean up interval on component unmount
    return () => clearInterval(interval);
  };
  
  return (
    <Container maxWidth="lg">
      <Paper elevation={3} sx={{ p: 4, my: 4 }}>
        <Typography variant="h4" gutterBottom>
          School Schedule Optimization
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ my: 2 }}>
            <AlertTitle>Error</AlertTitle>
            {error}
          </Alert>
        )}
        
        {successMessage && (
          <Alert severity="success" sx={{ my: 2 }}>
            <AlertTitle>Success</AlertTitle>
            {successMessage}
          </Alert>
        )}
        
        {jobStatus && (
          <Alert severity="info" sx={{ my: 2 }}>
            <AlertTitle>Job Status: {jobStatus.status}</AlertTitle>
            {jobStatus.message}
          </Alert>
        )}
        
        <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
          Upload School Data Files
        </Typography>
        
        <Grid container spacing={3}>
          {Object.entries(fileMetadata).map(([fileType, metadata]) => (
            <Grid item xs={12} md={6} key={fileType}>
              <FileUpload
                label={metadata.label + (metadata.required ? ' *' : ' (Optional)')}
                helperText={metadata.help}
                accept=".csv"
                onChange={(file) => handleFileSelect(fileType as keyof FileState, file)}
                disabled={uploading}
                value={files[fileType as keyof FileState]}
              />
              
              {uploadProgress[fileType] !== undefined && (
                <Box sx={{ mt: 1 }}>
                  <LinearProgress 
                    variant="determinate" 
                    value={uploadProgress[fileType]} 
                    sx={{ height: 8, borderRadius: 4 }} 
                  />
                  <Typography variant="caption" display="block" textAlign="right">
                    {Math.round(uploadProgress[fileType])}%
                  </Typography>
                </Box>
              )}
            </Grid>
          ))}
        </Grid>
        
        <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
          <Button
            variant="contained"
            color="primary"
            size="large"
            startIcon={<PlayArrowIcon />}
            onClick={startOptimizationJob}
            disabled={!allRequiredFilesUploaded() || uploading || jobStatus?.status === 'RUNNING'}
            sx={{ py: 1.5, px: 4, borderRadius: 2 }}
          >
            Find Optimal Schedule
          </Button>
        </Box>
        
        {jobStatus?.status === 'SUCCEEDED' && (
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
            <Button
              variant="outlined"
              color="primary"
              onClick={() => window.location.href = '/results'}
            >
              View Results
            </Button>
          </Box>
        )}
      </Paper>
    </Container>
  );
};

export default ScheduleOptimizer;