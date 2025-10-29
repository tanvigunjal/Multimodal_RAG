import { API_BASE_URL } from './api.js';

export function initUploads() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const uploadButton = document.getElementById('upload-button');
  const uploadStatus = document.getElementById('upload-status');

  if (!dropZone || !fileInput || !uploadButton || !uploadStatus) return;

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

  dropZone.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', () => {
    filesToUpload = Array.from(fileInput.files);
    updateFileList();
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    filesToUpload = Array.from(e.dataTransfer.files);
    updateFileList();
  });

  uploadButton.addEventListener('click', async () => {
    if (filesToUpload.length === 0) {
      uploadStatus.textContent = 'Please select files to upload.';
      return;
    }

    uploadButton.disabled = true;
    uploadStatus.textContent = 'Uploading... Please wait.';

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

      uploadStatus.textContent = `Uploading ${filesToUpload.length} file(s)...`;

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      uploadStatus.textContent = 'Processing... This may take a moment.';

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || 'Upload failed.');
      }

      uploadStatus.textContent = result.message || 'Upload successful!';
      filesToUpload = [];
      fileInput.value = '';
      updateFileList();

    } catch (err) {
      console.error('Upload error:', err);
      uploadStatus.textContent = `Error: ${err.message}`;
    } finally {
      uploadButton.disabled = false;
      setTimeout(() => {
        if (!filesToUpload.length) {
          uploadStatus.textContent = '';
        }
      }, 5000);
    }
  });
}