import React, { useState, useCallback } from 'react';
import './FileUploader.css';

interface FileUploaderProps {
  fileType: string;
  acceptedFileTypes?: string;
  maxFileSize?: number;
  onFileSelected: (file: File) => void;
  onFileRemoved: () => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({
  fileType,
  acceptedFileTypes = '.csv',
  maxFileSize = 5 * 1024 * 1024, // 5MB default
  onFileSelected,
  onFileRemoved
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const selectedFile = files[0];

    // Check file size
    if (selectedFile.size > maxFileSize) {
      setError(`File size exceeds the maximum allowed size (${maxFileSize / 1024 / 1024}MB)`);
      return;
    }

    // Check file type
    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setError('Only CSV files are accepted');
      return;
    }

    // Clear any previous errors
    setError(null);
    setFile(selectedFile);
    onFileSelected(selectedFile);
  };

  // Handle file removal
  const handleRemoveFile = () => {
    setFile(null);
    setError(null);
    onFileRemoved();
  };

  return (
    <div className="file-uploader-container">
      <div className={`file-uploader ${file ? 'has-file' : ''} ${error ? 'has-error' : ''}`}>
        {file ? (
          <div className="file-info">
            <div className="file-icon">📄</div>
            <div className="file-details">
              <p className="file-name">{file.name}</p>
              <p className="file-size">{(file.size / 1024).toFixed(2)} KB</p>
            </div>
            <button 
              className="remove-file" 
              onClick={handleRemoveFile}
              aria-label="Remove file"
            >
              ✕
            </button>
          </div>
        ) : (
          <div className="upload-prompt">
            <div className="upload-icon">📁</div>
            <p className="upload-text">
              Click to select your {fileType} file
            </p>
            <p className="upload-info">CSV format only, max {maxFileSize / 1024 / 1024}MB</p>
            <input 
              type="file" 
              accept={acceptedFileTypes} 
              onChange={handleFileChange} 
              className="file-input"
            />
          </div>
        )}
        
        {error && <p className="error-message">{error}</p>}
      </div>
    </div>
  );
};

export default FileUploader;