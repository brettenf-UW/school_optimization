import { Amplify } from 'aws-amplify';
import { uploadData, getUrl } from 'aws-amplify/storage';
import { fetchAuthSession } from 'aws-amplify/auth';

// For LocalStack development
// Will be dynamically determined by App component, default to false for production testing
let IS_LOCAL_DEV = false;

// Base URLs for API
const PROD_API_URL = 'http://54.202.229.226:8000/api'; // Use EC2 direct URL for testing
const LOCAL_API_URL = 'http://localhost:8000/api';

// For debugging - log all API URLs
console.log('API URLs configured:', { 
  PROD_API_URL, 
  LOCAL_API_URL, 
  IS_LOCAL_DEV 
});

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
    // Always use direct API call instead of simulation
    console.log('Production mode: Starting real optimization job', { 
      schoolId, 
      optimizationType,
      apiEndpoint: API_BASE_URL 
    });
    
    try {
      // Always communicate directly with the API
      const response = await fetch(`${API_BASE_URL}/jobs/schedule`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer dev-token' // For testing
        },
        body: JSON.stringify({
          school_id: schoolId,
          job_type: "SCHEDULE_OPTIMIZATION",
          parameters: {
            optimization_type: optimizationType
          }
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to start optimization job');
      }
      
      const data = await response.json();
      console.log('API job response:', data);
      return { jobId: data.job_id || data.jobId };
    } catch (error) {
      console.error('Error starting optimization job:', error);
      throw error; // Re-throw to allow caller to handle the error
    }
  },

  /**
   * Get the status of an optimization job
   * @param jobId The job ID
   */
  getJobStatus: async (jobId: string) => {
    // Always use direct API call for job status
    console.log('Getting real job status for job ID:', jobId);
    
    try {
      // Direct API call
      const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/status`, {
        headers: {
          'Authorization': 'Bearer dev-token' // For testing
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to get job status');
      }
      
      const data = await response.json();
      console.log('Job status response:', data);
      
      // Transform the API response to match the expected format
      return {
        id: data.job_id || jobId,
        status: data.status,
        message: data.error_message || `Job is ${data.status}`,
        progress: data.progress,
        results: data.result_files || []
      };
    } catch (error) {
      console.error('Error getting job status:', error);
      
      // Return a fallback status in case of error
      return {
        id: jobId,
        status: 'ERROR',
        message: `Error fetching job status: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  },

  /**
   * Upload school data files
   * @param schoolId School identifier
   * @param files FormData object containing files to upload
   */
  uploadSchoolData: async (schoolId: string, files: FormData): Promise<any> => {
    // Always use direct API call
    console.log('Production mode: Uploading files to real API', {
      schoolId,
      fileCount: Array.from(files.keys()).filter(key => key !== 'school_id').length,
      apiEndpoint: API_BASE_URL
    });
    
    try {
      // Send files to API
      const response = await fetch(`${API_BASE_URL}/upload/school-data`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer dev-token' // For testing
        },
        body: files
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to upload files');
      }
      
      const data = await response.json();
      console.log('File upload response:', data);
      return data;
    } catch (error) {
      console.error('Error uploading files to API:', error);
      throw error; // Re-throw to allow caller to handle the error
    }
  }
};

export default EchelonAPI;