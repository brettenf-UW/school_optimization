import { Amplify } from 'aws-amplify';
import { uploadData, getUrl } from 'aws-amplify/storage';
import { fetchAuthSession } from 'aws-amplify/auth';

// For LocalStack development
// Will be dynamically determined by App component, default to false for production testing
let IS_LOCAL_DEV = false;

// Base URLs for API
const PROD_API_URL = 'http://54.202.229.226:8000/api'; // Use EC2 direct URL for testing
const LOCAL_API_URL = 'http://localhost:8000/api';

// Use LocalStack API endpoint if available, otherwise use production
const getApiEndpoint = () => {
  return IS_LOCAL_DEV ? LOCAL_API_URL : PROD_API_URL;
};

// API_BASE_URL will be updated dynamically
let API_BASE_URL = getApiEndpoint();

// Function to update LocalStack status from App component
export const setLocalStackAvailability = (isAvailable: boolean) => {
  IS_LOCAL_DEV = isAvailable;
  // Update API endpoint when LocalStack status changes
  API_BASE_URL = getApiEndpoint();
  console.log(`LocalStack availability set to: ${isAvailable}`);
  console.log(`API endpoint set to: ${API_BASE_URL}`);
};
const LOCAL_AWS_ENDPOINT = 'http://localhost:4566';
const LOCAL_S3_BUCKET = 'dev-echelon-data';

// Configure Amplify for local development
if (IS_LOCAL_DEV) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: 'us-west-2_gVCuWb3dQ', // From LocalStack init
        userPoolClientId: '2vabalt8ij3kfp4tibhahce7ds', // From LocalStack init
        identityPoolId: 'us-west-2:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
        loginWith: {
          email: true,
          username: true,
          phone: false
        },
        // For local development, we'll use a dummy endpoint
        endpoint: LOCAL_AWS_ENDPOINT
      }
    },
    Storage: {
      S3: {
        bucket: LOCAL_S3_BUCKET,
        region: 'us-west-2',
        // For local development, we'll use LocalStack
        endpoint: LOCAL_AWS_ENDPOINT,
        customEndpoint: LOCAL_AWS_ENDPOINT,
        dangerouslyConnectToHttpEndpointForTesting: true
      }
    }
  });
}

/**
 * Service for file uploads and API interactions
 * Uses LocalStack for local development
 */
export const EchelonAPI = {
  /**
   * Upload files to S3 storage
   * @param schoolId The school ID
   * @param files Object containing the files to upload with file types as keys
   * @param progressCallback Optional callback for progress updates
   */
  uploadFiles: async (
    schoolId: string, 
    files: Record<string, File>, 
    progressCallback?: (fileType: string, progress: number) => void
  ): Promise<boolean> => {
    try {
      if (IS_LOCAL_DEV) {
        // SimulateUpload with LocalStack
        console.log('LocalStack mode: Uploading files to LocalStack S3');
        
        const uploadPromises = Object.entries(files).map(async ([fileType, file]) => {
          const s3Path = `input-data/${schoolId}/${fileType}/${file.name}`;
          
          try {
            // For LocalStack, we use simpler upload to avoid issues
            const result = await uploadData({
              key: s3Path,
              data: file,
              options: {
                contentType: 'text/csv',
                onProgress: event => {
                  if (progressCallback) {
                    progressCallback(fileType, (event.loaded / event.total) * 100);
                  }
                }
              }
            });
            
            console.log(`Successfully uploaded ${fileType} file to ${s3Path} in LocalStack`);
            return true;
          } catch (error) {
            console.error(`Error uploading ${fileType} to LocalStack:`, error);
            return false;
          }
        });

        const results = await Promise.all(uploadPromises);
        return results.every(result => result === true);
      } else {
        // Simulate for simple development when LocalStack isn't available
        const uploadPromises = Object.entries(files).map(async ([fileType, file]) => {
          console.log(`Simulated upload for ${fileType}: ${file.name}`);
          
          // Simulate upload progress
          for (let progress = 0; progress <= 100; progress += 10) {
            if (progressCallback) {
              progressCallback(fileType, progress);
            }
            
            // Short delay to simulate network activity
            await new Promise(resolve => setTimeout(resolve, 200));
          }
          
          return true;
        });

        const results = await Promise.all(uploadPromises);
        return results.every(result => result === true);
      }
    } catch (error) {
      console.error('Error uploading files:', error);
      return false;
    }
  },

  /**
   * Start an optimization job
   * @param schoolId The school ID
   * @param optimizationType The type of optimization to run
   */
  startOptimizationJob: async (schoolId: string, optimizationType: string = 'milp_soft'): Promise<{jobId: string}> => {
    if (IS_LOCAL_DEV) {
      try {
        // When using LocalStack with API, use fetch to communicate with the API
        const response = await fetch(`${API_BASE_URL}/jobs`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // In development, we can use a simulated token
            'Authorization': 'Bearer dev-token'
          },
          body: JSON.stringify({
            schoolId,
            optimizationType
          })
        });
        
        if (!response.ok) {
          throw new Error('Failed to start optimization job');
        }
        
        const data = await response.json();
        return { jobId: data.jobId || `dev-job-${Date.now()}` };
      } catch (error) {
        console.error('Error starting job with LocalStack:', error);
        // Fallback to simulation if the API call fails
        return { jobId: `dev-job-${Date.now()}` };
      }
    } else {
      // Simulate job submission for development
      console.log('Development mode: Simulating job submission', { 
        schoolId, 
        optimizationType 
      });
      
      // Short delay to simulate network latency
      await new Promise(resolve => setTimeout(resolve, 500));
      
      return { jobId: `dev-job-${Date.now()}` };
    }
  },

  /**
   * Get the status of an optimization job
   * @param jobId The job ID
   */
  getJobStatus: async (jobId: string) => {
    if (IS_LOCAL_DEV && !jobId.startsWith('dev-job')) {
      try {
        // When using LocalStack with API, use fetch
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/status`, {
          headers: {
            'Authorization': 'Bearer dev-token'
          }
        });
        
        if (!response.ok) {
          throw new Error('Failed to get job status');
        }
        
        return await response.json();
      } catch (error) {
        console.error('Error getting job status from LocalStack:', error);
        // Fallback to simulation
      }
    }
    
    // If LocalStack call failed or we're not using it, simulate the response
    // In development, simulate job status based on elapsed time
    const jobIdTimestamp = parseInt(jobId.split('-')[2] || Date.now().toString());
    const elapsedTime = Date.now() - jobIdTimestamp;
    
    // Add a small delay to make it feel more realistic
    await new Promise(resolve => setTimeout(resolve, 200)); 
    
    if (elapsedTime < 3000) {
      return {
        id: jobId,
        status: 'SUBMITTED',
        message: 'Optimization job submitted successfully! (Development Mode)'
      };
    } else if (elapsedTime < 10000) {
      return {
        id: jobId,
        status: 'RUNNING',
        message: 'Optimization is in progress (Development Mode)'
      };
    } else {
      return {
        id: jobId,
        status: 'SUCCEEDED',
        message: 'Optimization completed successfully! (Development Mode)',
        results: [
          { name: 'Master_Schedule.csv', url: '#' },
          { name: 'Student_Assignments.csv', url: '#' },
          { name: 'Teacher_Schedule.csv', url: '#' }
        ]
      };
    }
  },

  /**
   * Upload school data files
   * @param schoolId School identifier
   * @param files FormData object containing files to upload
   */
  uploadSchoolData: async (schoolId: string, files: FormData): Promise<any> => {
    if (IS_LOCAL_DEV) {
      try {
        // When using LocalStack with API
        console.log('LocalStack mode: Uploading files to LocalStack via API');
        
        // Use fetch to communicate with your local API
        const response = await fetch(`${API_BASE_URL}/upload/school-data`, {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer dev-token'
          },
          body: files
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to upload files');
        }
        
        return await response.json();
      } catch (error) {
        console.error('Error uploading to LocalStack API:', error);
        
        // If API call fails, fallback to simulation
        console.log('Falling back to simulation...');
        
        // Log what would be uploaded
        console.log('Development mode: Simulating file upload', {
          schoolId,
          fileCount: Array.from(files.keys()).filter(key => key !== 'school_id').length
        });
        
        // Return a simulated successful response after a delay
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        return {
          success: true,
          message: 'Files uploaded successfully (Development Mode)',
          fileCount: Array.from(files.keys()).filter(key => key !== 'school_id').length
        };
      }
    } else {
      // Regular simulation
      console.log('Development mode: Simulating file upload', {
        schoolId,
        fileCount: Array.from(files.keys()).filter(key => key !== 'school_id').length
      });
      
      // Return a simulated successful response after a delay
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      return {
        success: true,
        message: 'Files uploaded successfully (Development Mode)',
        fileCount: Array.from(files.keys()).filter(key => key !== 'school_id').length
      };
    }
  }
};

export default EchelonAPI;