import React, { useState, useEffect } from 'react';
import './App.css';
import FileUploader from './components/upload/FileUploader';
import JobStatus from './components/JobStatus';
import EchelonAPI, { setLocalStackAvailability } from './services/api';

interface UploadFiles {
  studentInfo?: File;  
  studentPreferences?: File;
  teacherInfo?: File;
  teacherUnavailability?: File;
  sectionsInfo?: File;
  periods?: File;
}

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [files, setFiles] = useState<UploadFiles>({});
  const [schoolId, setSchoolId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStarted, setJobStarted] = useState(false);
  const [isLocalStackRunning, setIsLocalStackRunning] = useState(false);
  
  // Force production mode for AWS Batch testing
  useEffect(() => {
    // Skip actual LocalStack check and force production mode
    console.log('Forcing production mode for AWS Batch testing');
    setIsLocalStackRunning(true); // Pretend LocalStack is running to bypass simulation
    setLocalStackAvailability(true); // Update API service to production mode
  }, []);
  
  // File handlers
  const handleFileSelected = (fileType: keyof UploadFiles) => (file: File) => {
    setFiles(prevFiles => ({
      ...prevFiles,
      [fileType]: file
    }));
  };
  
  const handleFileRemoved = (fileType: keyof UploadFiles) => () => {
    setFiles(prevFiles => {
      const newFiles = { ...prevFiles };
      delete newFiles[fileType];
      return newFiles;
    });
  };

  // Check if form is valid
  const isFormValid = () => {
    // School ID must be present
    if (schoolId.trim() === '') {
      return false;
    }
    
    // Required fields must be present (teacherUnavailability is optional)
    const requiredFields = [
      'studentInfo',
      'studentPreferences',
      'teacherInfo',
      'sectionsInfo',
      'periods'
    ];
    
    // Check that all required fields have files
    return requiredFields.every(field => files[field as keyof UploadFiles] !== undefined);
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isFormValid()) {
      const missingFields = [];
      
      if (schoolId.trim() === '') {
        missingFields.push('School ID');
      }
      
      const requiredFields = [
        { key: 'studentInfo', label: 'Student Information' },
        { key: 'studentPreferences', label: 'Student Preferences' },
        { key: 'teacherInfo', label: 'Teacher Information' },
        { key: 'sectionsInfo', label: 'Sections Information' },
        { key: 'periods', label: 'School Periods' }
      ];
      
      requiredFields.forEach(field => {
        if (!files[field.key as keyof UploadFiles]) {
          missingFields.push(field.label);
        }
      });
      
      setError(`Please provide the following required information: ${missingFields.join(', ')}`);
      return;
    }
    
    setIsSubmitting(true);
    setError(null);
    
    try {
      // Create form data
      const formData = new FormData();
      formData.append('school_id', schoolId);
      
      // Add files to form data
      if (files.studentInfo) formData.append('student_info_file', files.studentInfo);
      if (files.studentPreferences) formData.append('student_preferences_file', files.studentPreferences);
      if (files.teacherInfo) formData.append('teacher_info_file', files.teacherInfo);
      if (files.teacherUnavailability) formData.append('teacher_unavailability_file', files.teacherUnavailability);
      if (files.sectionsInfo) formData.append('sections_info_file', files.sectionsInfo);
      if (files.periods) formData.append('periods_file', files.periods);
      
      // Upload files via API service
      const response = await EchelonAPI.uploadSchoolData(schoolId, formData);
      console.log('Upload response:', response);
      
      // After successful upload, start an optimization job
      try {
        const jobResponse = await EchelonAPI.startOptimizationJob(schoolId);
        console.log('Job started:', jobResponse);
        
        // Set job tracking state
        setJobId(jobResponse.jobId);
        setJobStarted(true);
        
        // Show success message
        setUploadSuccess(true);
        
        // Reset form fields but keep job status visible
        setTimeout(() => {
          setFiles({});
          setSchoolId('');
          setUploadSuccess(false);
          // Don't navigate away immediately so user can see job status
        }, 3000);
      } catch (jobError: any) {
        console.error('Error starting optimization job:', jobError);
        setError(jobError.message || 'Failed to start optimization job');
      }
    } catch (error: any) {
      console.error('Error uploading files:', error);
      setError(error.message || 'Failed to upload files');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Mock login function
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoggedIn(true);
    setShowLoginModal(false);
  };
  
  // Mock logout function
  const handleLogout = () => {
    setIsLoggedIn(false);
    setActiveTab('dashboard');
  };

  // Rendering simple test page with file upload
  console.log("App component rendering - file upload test mode");
  return (
    <div style={{ 
      padding: '20px', 
      maxWidth: '800px', 
      margin: '0 auto', 
      fontFamily: 'Arial, sans-serif',
      textAlign: 'center'
    }}>
      <h1>Echelon Platform</h1>
      <p>This is a minimal test page to diagnose rendering issues.</p>
      
      <form onSubmit={handleSubmit} style={{ marginTop: '30px', textAlign: 'left' }}>
        {/* LocalStack status indicator */}
        <div style={{ 
          backgroundColor: isLocalStackRunning ? 'rgba(0, 170, 85, 0.1)' : 'rgba(255, 193, 7, 0.1)', 
          color: isLocalStackRunning ? '#00aa55' : '#ff9800', 
          padding: '10px 15px', 
          borderRadius: '4px', 
          marginBottom: '15px',
          display: 'flex',
          alignItems: 'center',
          fontSize: '0.9rem'
        }}>
          <span style={{ fontSize: '1.1rem', marginRight: '10px' }}>
            {isLocalStackRunning ? '✓' : '⚠️'}
          </span>
          {isLocalStackRunning 
            ? 'LocalStack is running - AWS services available locally' 
            : 'LocalStack not detected - using simulation mode'}
        </div>
        
        {uploadSuccess && (
          <div style={{ 
            backgroundColor: 'rgba(0, 170, 85, 0.1)', 
            color: '#00aa55', 
            padding: '15px', 
            borderRadius: '4px', 
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center'
          }}>
            <span style={{ fontSize: '1.5rem', marginRight: '10px' }}>✓</span>
            Files uploaded successfully!
          </div>
        )}
        
        {/* Show Job Status when a job is in progress */}
        {jobStarted && jobId && (
          <div style={{ marginBottom: '20px' }}>
            <h3>Optimization Job Status</h3>
            <JobStatus 
              jobId={jobId}
              onSuccess={() => {
                console.log('Job completed successfully');
                // Additional success handling if needed
              }}
              onError={(errorMsg) => {
                setError(`Optimization failed: ${errorMsg}`);
              }}
            />
            
            <div style={{ marginTop: '15px' }}>
              <button
                onClick={() => {
                  setJobStarted(false);
                  setJobId(null);
                }}
                style={{
                  padding: '8px 16px',
                  background: '#f0f0f0',
                  color: '#333',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Start New Optimization
              </button>
            </div>
          </div>
        )}
        
        {/* Hide the form when job is in progress */}
        {!jobStarted && (
          <>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
                School ID
              </label>
              <input 
                type="text" 
                value={schoolId}
                onChange={(e) => setSchoolId(e.target.value)}
                placeholder="Enter your school ID"
                style={{ 
                  width: '100%', 
                  padding: '10px', 
                  borderRadius: '4px', 
                  border: '1px solid #ccc' 
                }}
                required
              />
            </div>
            
            <h3>Upload Files</h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
              <div>
                <h4>Student Information</h4>
                <FileUploader
                  fileType="Student Information"
                  onFileSelected={handleFileSelected('studentInfo')}
                  onFileRemoved={handleFileRemoved('studentInfo')}
                />
                <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '5px' }}>
                  CSV with student records (ID, grade level, etc.)
                </p>
              </div>
              
              <div>
                <h4>Student Preferences</h4>
                <FileUploader
                  fileType="Student Preferences"
                  onFileSelected={handleFileSelected('studentPreferences')}
                  onFileRemoved={handleFileRemoved('studentPreferences')}
                />
                <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '5px' }}>
                  CSV with student course requests and rankings
                </p>
              </div>
              
              <div>
                <h4>Teacher Information</h4>
                <FileUploader
                  fileType="Teacher Information"
                  onFileSelected={handleFileSelected('teacherInfo')}
                  onFileRemoved={handleFileRemoved('teacherInfo')}
                />
                <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '5px' }}>
                  CSV with teacher records and attributes
                </p>
              </div>
              
              <div>
                <h4>Teacher Unavailability</h4>
                <FileUploader
                  fileType="Teacher Unavailability"
                  onFileSelected={handleFileSelected('teacherUnavailability')}
                  onFileRemoved={handleFileRemoved('teacherUnavailability')}
                />
                <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '5px' }}>
                  CSV showing periods teachers cannot teach (optional)
                </p>
              </div>
              
              <div>
                <h4>Sections Information</h4>
                <FileUploader
                  fileType="Sections Information"
                  onFileSelected={handleFileSelected('sectionsInfo')}
                  onFileRemoved={handleFileRemoved('sectionsInfo')}
                />
                <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '5px' }}>
                  CSV with course sections and capacities
                </p>
              </div>
              
              <div>
                <h4>School Periods</h4>
                <FileUploader
                  fileType="School Periods"
                  onFileSelected={handleFileSelected('periods')}
                  onFileRemoved={handleFileRemoved('periods')}
                />
                <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '5px' }}>
                  CSV defining the school schedule periods
                </p>
              </div>
            </div>
            
            {error && (
              <div style={{ 
                backgroundColor: 'rgba(255, 60, 0, 0.1)', 
                color: '#ff3c00', 
                padding: '10px 15px', 
                borderRadius: '4px', 
                marginBottom: '20px' 
              }}>
                {error}
              </div>
            )}
            
            <button 
              type="submit"
              disabled={isSubmitting || !isFormValid()}
              style={{
                padding: '12px 24px',
                background: isFormValid() ? '#0077ff' : '#cccccc',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                fontSize: '16px',
                cursor: isFormValid() ? 'pointer' : 'not-allowed',
                width: '100%'
              }}
            >
              {isSubmitting ? 'Uploading...' : 'Upload Files'}
            </button>
          </>
        )}
      </form>
      
      {/* Hide the fallback content when React loads */}
      <script dangerouslySetInnerHTML={{
        __html: `
          // Hide the fallback content since React has loaded
          const fallback = document.getElementById('fallback');
          if (fallback) {
            fallback.style.display = 'none';
            console.log('React loaded, hiding fallback content');
          }
        `
      }} />
    </div>
  );

}

export default App;