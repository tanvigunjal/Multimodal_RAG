import { API_BASE_URL } from './api.js';

// Store event handlers for cleanup
let eventHandlers = {
  dropZone: {},
  fileInput: {},
  uploadButton: {}
};

export function initUploads() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const uploadButton = document.getElementById('upload-button');
  const uploadStatus = document.getElementById('upload-status');

  if (!dropZone || !fileInput || !uploadButton || !uploadStatus) return;

  // Clean up existing event listeners
  cleanup();

  let filesToUpload = [];

  const updateFileList = () => {
    if (filesToUpload.length > 0) {
      uploadStatus.textContent = `${filesToUpload.length} file(s) selected.`;
      uploadButton.style.display = 'block';
    } else {
      uploadStatus.textContent = '';
      uploadButton.style.display = 'none';
    }
  };

  // Store handlers for cleanup
  eventHandlers.dropZone.click = () => fileInput.click();
  eventHandlers.fileInput.change = () => {
    filesToUpload = Array.from(fileInput.files);
    updateFileList();
  };
  eventHandlers.dropZone.dragover = (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  };
  eventHandlers.dropZone.dragleave = () => {
    dropZone.classList.remove('drag-over');
  };
  eventHandlers.dropZone.drop = (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    filesToUpload = Array.from(e.dataTransfer.files);
    updateFileList();
  };

  // Add event listeners
  dropZone.addEventListener('click', eventHandlers.dropZone.click);
  fileInput.addEventListener('change', eventHandlers.fileInput.change);
  dropZone.addEventListener('dragover', eventHandlers.dropZone.dragover);
  dropZone.addEventListener('dragleave', eventHandlers.dropZone.dragleave);
  dropZone.addEventListener('drop', eventHandlers.dropZone.drop);

  // Store upload button handler
  eventHandlers.uploadButton.click = async () => {
    if (filesToUpload.length === 0) {
      uploadStatus.textContent = 'Please select files to upload.';
      return;
    }

    uploadButton.disabled = true;
    uploadButton.style.display = 'none';
    
    // Clear any existing status
    uploadStatus.innerHTML = '';
    
    // Create status container
    const container = document.createElement('div');
    container.className = 'upload-status-container';
    
    const statusText = document.createElement('div');
    statusText.className = 'upload-status-text';
    container.appendChild(statusText);
    
    const progressBar = document.createElement('div');
    progressBar.className = 'upload-progress-bar';
    const progressInner = document.createElement('div');
    progressInner.className = 'upload-progress-inner';
    progressBar.appendChild(progressInner);
    container.appendChild(progressBar);
    
    uploadStatus.appendChild(container);

    try {
      const formData = new FormData();
      let endpoint = '/upload-documents';

      // Check if the upload is a single zip file
      if (filesToUpload.length === 1 && filesToUpload[0].type === 'application/zip') {
        formData.append('file', filesToUpload[0]);
        endpoint = '/upload-zip';
      } else {
        filesToUpload.forEach(file => formData.append('files', file));
      }

      const updateProgress = (message, progress, color = null) => {
        statusText.textContent = message;
        progressInner.style.width = `${progress}%`;
        if (color) {
          progressInner.style.backgroundColor = color;
        }
      };

      updateProgress('Preparing to upload files...', 5);
      updateProgress('Uploading files to server...', 25);

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || 'Upload failed.');
      }

      const pollJobStatus = async (jobs) => {
        const pollInterval = 1000; // Poll every second
        const maxAttempts = 180; // Maximum 3 minutes of polling
        let attempts = 0;
        console.log('Starting status polling for jobs:', jobs);
        
        while (attempts < maxAttempts) {
          try {
            const statuses = await Promise.all(
              jobs.map(job => 
                fetch(`${API_BASE_URL}/job-status/${job.job_id}`)
                  .then(r => r.json())
                  .catch(e => ({ 
                    status: "FAILED", 
                    progress: "0", 
                    current_step: `Error: ${e.message}`,
                    file_name: job.file_name 
                  }))
              )
            );
            
            // Calculate overall progress
            const totalProgress = statuses.reduce((sum, status) => sum + parseInt(status.progress || 0), 0) / statuses.length;
            const inProgress = statuses.some(status => status.status === "PROCESSING");
            const allComplete = statuses.every(status => ["SUCCESS", "DUPLICATE", "FAILED"].includes(status.status));
            
            if (allComplete) {
              const successCount = statuses.filter(s => s.status === "SUCCESS").length;
              const duplicateCount = statuses.filter(s => s.status === "DUPLICATE").length;
              const failedCount = statuses.filter(s => s.status === "FAILED").length;
              
              let message = '';
              if (successCount > 0) message += `✓ ${successCount} file(s) processed successfully\n`;
              if (duplicateCount > 0) message += `ℹ ${duplicateCount} file(s) already exist in database\n`;
              if (failedCount > 0) message += `✗ ${failedCount} file(s) failed to process\n`;
              
              updateProgress(
                message.trim(),
                100,
                failedCount > 0 ? '#dc3545' : '#4CAF50'
              );
              return;
            }
            
            if (inProgress) {
              const currentSteps = statuses
                .filter(s => s.current_step)
                .map(s => `${s.file_name}: ${s.current_step}`)
                .join('\n');
              updateProgress(currentSteps, 50 + (totalProgress / 2));
            } else {
              updateProgress('Waiting for processing to begin...', 50);
            }
          } catch (error) {
            console.error('Error polling job status:', error);
            statusText.textContent = `Error checking status: ${error.message}`;
          }
          
          attempts++;
          await new Promise(resolve => setTimeout(resolve, pollInterval));
        }
        
        // If we reach here, polling timed out
        statusText.textContent = 'Processing timeout. Please check job status manually.';
        progressInner.style.width = '100%';
        progressInner.style.backgroundColor = '#ffc107';
      };

      console.log('Upload successful, starting status polling:', result);
      await pollJobStatus(result.jobs);

      filesToUpload = [];
      fileInput.value = '';
      updateFileList();
      
      // Auto-hide success message after 30 seconds
      setTimeout(() => {
        if (uploadStatus.contains(container)) {
          container.style.opacity = '0';
          setTimeout(() => container.remove(), 300);
        }
      }, 30000);

    } catch (err) {
      console.error('Upload error:', err);
      container.classList.add('error');
      statusText.innerHTML = `⚠️ Error: ${err.message}`;
      progressInner.style.width = '100%';
      progressInner.style.backgroundColor = '#dc3545';
      
      // Keep error message visible for 10 seconds
      setTimeout(() => {
        container.style.opacity = '0';
        setTimeout(() => {
          if (uploadStatus.contains(container)) {
            uploadStatus.removeChild(container);
          }
        }, 300);
      }, 10000);
    } finally {
      uploadButton.disabled = false;
      uploadButton.style.display = 'block';
    }
  };

  // Add upload button listener
  uploadButton.addEventListener('click', eventHandlers.uploadButton.click);
}

export function cleanup() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const uploadButton = document.getElementById('upload-button');
  
  if (dropZone) {
    Object.entries(eventHandlers.dropZone).forEach(([event, handler]) => {
      dropZone.removeEventListener(event, handler);
    });
  }
  
  if (fileInput) {
    Object.entries(eventHandlers.fileInput).forEach(([event, handler]) => {
      fileInput.removeEventListener(event, handler);
    });
  }
  
  if (uploadButton) {
    Object.entries(eventHandlers.uploadButton).forEach(([event, handler]) => {
      uploadButton.removeEventListener(event, handler);
    });
  }
  
  // Reset event handlers
  eventHandlers = {
    dropZone: {},
    fileInput: {},
    uploadButton: {}
  };
}