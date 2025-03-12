import React, { useState, useRef } from 'react';
import {
  Box,
  Button,
  Typography,
  Paper,
  TextField,
  Tooltip,
  IconButton
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import InfoIcon from '@mui/icons-material/Info';
import ArticleIcon from '@mui/icons-material/Article';

interface FileUploadProps {
  label: string;
  helperText?: string;
  accept?: string;
  onChange: (file: File | null) => void;
  disabled?: boolean;
  value: File | null;
}

const FileUpload: React.FC<FileUploadProps> = ({
  label,
  helperText,
  accept = '*',
  onChange,
  disabled = false,
  value
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const handleButtonClick = () => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };
  
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      onChange(files[0]);
    }
    // Reset input value so the same file can be selected again if removed
    event.target.value = '';
  };
  
  const handleRemoveFile = () => {
    onChange(null);
  };
  
  return (
    <Paper
      elevation={1}
      sx={{
        p: 2,
        borderRadius: 2,
        border: '1px dashed',
        borderColor: value ? 'success.main' : 'divider',
        backgroundColor: value ? 'success.light' : 'background.paper',
        opacity: disabled ? 0.7 : 1,
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          borderColor: !disabled ? 'primary.main' : 'divider',
        }
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle1" component="div" sx={{ fontWeight: 'medium', display: 'flex', alignItems: 'center' }}>
          {label}
          {helperText && (
            <Tooltip title={helperText} arrow placement="top">
              <IconButton size="small" sx={{ ml: 0.5 }}>
                <InfoIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Typography>
        
        {!value ? (
          <Button
            variant="outlined"
            startIcon={<CloudUploadIcon />}
            onClick={handleButtonClick}
            disabled={disabled}
            size="small"
          >
            Upload
          </Button>
        ) : (
          <IconButton 
            color="error" 
            onClick={handleRemoveFile}
            disabled={disabled}
            size="small"
          >
            <DeleteIcon />
          </IconButton>
        )}
      </Box>
      
      {value && (
        <Box 
          sx={{ 
            mt: 1, 
            display: 'flex', 
            alignItems: 'center',
            p: 1, 
            borderRadius: 1,
            bgcolor: 'background.paper'
          }}
        >
          <ArticleIcon color="primary" sx={{ mr: 1 }} />
          <Typography variant="body2" sx={{ flexGrow: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {value.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {(value.size / 1024).toFixed(1)} KB
          </Typography>
        </Box>
      )}
      
      <input
        type="file"
        ref={fileInputRef}
        accept={accept}
        onChange={handleFileChange}
        style={{ display: 'none' }}
        disabled={disabled}
      />
    </Paper>
  );
};

export default FileUpload;