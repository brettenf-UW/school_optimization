import React, { useState, useEffect } from 'react';
import EchelonAPI from '../services/api';
import './JobStatus.css';

interface JobStatusProps {
  jobId: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

interface JobStatusData {
  id: string;
  status: string;
  message: string;
  results?: any[];
}

const JobStatus: React.FC<JobStatusProps> = ({ jobId, onSuccess, onError }) => {
  const [status, setStatus] = useState<JobStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;
    let isMounted = true;

    // For development, we'll poll the simulated job status every 2 seconds
    const pollInterval = 2000;

    const fetchStatus = async () => {
      try {
        const jobStatus = await EchelonAPI.getJobStatus(jobId);
        
        if (isMounted) {
          setStatus(jobStatus);
          setLoading(false);

          if (jobStatus.status === 'SUCCEEDED' && onSuccess) {
            onSuccess();
          }

          if (jobStatus.status === 'FAILED' && onError) {
            onError(jobStatus.message);
          }

          // Continue polling if job is still running
          if (!['SUCCEEDED', 'FAILED'].includes(jobStatus.status)) {
            intervalId = setTimeout(fetchStatus, pollInterval);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Failed to fetch job status');
          setLoading(false);
          if (onError) onError(err.message || 'Failed to fetch job status');
        }
      }
    };

    // Start polling
    fetchStatus();

    // Clean up on unmount
    return () => {
      isMounted = false;
      if (intervalId) clearTimeout(intervalId);
    };
  }, [jobId, onSuccess, onError]);

  if (loading) {
    return (
      <div className="job-status-container">
        <div className="job-status loading">
          <div className="spinner"></div>
          <p>Loading job status...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="job-status-container">
        <div className="job-status error">
          <p>Error: {error}</p>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="job-status-container">
        <div className="job-status not-found">
          <p>Job not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="job-status-container">
      <div className={`job-status ${status.status.toLowerCase()}`}>
        <h3>Job Status: {status.status}</h3>
        <p>{status.message}</p>
        
        {status.status === 'RUNNING' && (
          <div className="progress-indicator">
            <div className="spinner"></div>
            <p>Optimization in progress...</p>
          </div>
        )}
        
        {status.status === 'SUCCEEDED' && status.results && (
          <div className="job-results">
            <h4>Results</h4>
            <ul>
              {status.results.map((result, index) => (
                <li key={index}>
                  <a href={result.url} target="_blank" rel="noreferrer">{result.name}</a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default JobStatus;