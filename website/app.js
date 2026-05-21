// AI Image Recognition Web Application

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

let selectedFile = null;
let currentImageId = null;

function initializeApp() {
    setupDropZone();
    setupFileInput();
    setupUploadButton();
    setupRefreshButton();
    setupModeSelector();
    loadRecentResults();
}

// ============================================
// Mode Selector Setup
// ============================================
function setupModeSelector() {
    const modeSelect = document.getElementById('modeSelect');
    const modeDescription = document.getElementById('modeDescription');
    
    const descriptions = {
        'celebrity': 'Identify famous people with Wikipedia bios',
        'labels': 'Detect objects, scenes, activities, and more'
    };
    
    modeSelect.addEventListener('change', () => {
        modeDescription.textContent = descriptions[modeSelect.value];
    });
}

function getSelectedMode() {
    return document.getElementById('modeSelect').value;
}

// ============================================
// Drop Zone Setup
// ============================================
function setupDropZone() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');

    dropZone.addEventListener('click', () => fileInput.click());

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
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });
}

function setupFileInput() {
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

function handleFileSelect(file) {
    // Validate file type
    if (!CONFIG.SUPPORTED_TYPES.includes(file.type)) {
        showStatus('error', 'Please select a JPEG or PNG image.');
        return;
    }

    // Validate file size
    if (file.size > CONFIG.MAX_FILE_SIZE) {
        showStatus('error', 'File size must be less than 5MB.');
        return;
    }

    selectedFile = file;
    
    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('imagePreview').src = e.target.result;
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('previewContainer').classList.remove('d-none');
        document.getElementById('dropZone').classList.add('has-file');
    };
    reader.readAsDataURL(file);

    // Enable upload button
    document.getElementById('uploadBtn').disabled = false;
    hideStatus();
}

// ============================================
// Upload Functionality
// ============================================
function setupUploadButton() {
    document.getElementById('uploadBtn').addEventListener('click', uploadImage);
}

async function uploadImage() {
    if (!selectedFile) return;

    const uploadBtn = document.getElementById('uploadBtn');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');

    try {
        // Disable button and show progress
        uploadBtn.disabled = true;
        progressContainer.classList.remove('d-none');
        updateProgress(10, 'Getting upload URL...');

        // Step 1: Get presigned URL
        const selectedMode = getSelectedMode();
        const presignResponse = await fetch(`${CONFIG.API_ENDPOINT}/upload`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: selectedFile.name,
                contentType: selectedFile.type,
                mode: selectedMode
            })
        });

        if (!presignResponse.ok) {
            throw new Error('Failed to get upload URL');
        }

        const { uploadUrl, imageId, objectKey } = await presignResponse.json();
        currentImageId = imageId;
        updateProgress(30, 'Uploading image...');

        // Step 2: Upload to S3
        const uploadResponse = await fetch(uploadUrl, {
            method: 'PUT',
            headers: { 'Content-Type': selectedFile.type },
            body: selectedFile
        });

        if (!uploadResponse.ok) {
            throw new Error('Failed to upload image');
        }

        updateProgress(60, 'Processing with AI...');

        // Step 3: Poll for results
        await pollForResults(imageId);

    } catch (error) {
        console.error('Upload error:', error);
        showStatus('error', `Upload failed: ${error.message}`);
        progressContainer.classList.add('d-none');
        uploadBtn.disabled = false;
    }
}

function updateProgress(percent, text) {
    document.getElementById('progressBar').style.width = `${percent}%`;
    document.getElementById('progressText').textContent = text;
}

// ============================================
// Results Polling
// ============================================
async function pollForResults(imageId, attempts = 0) {
    if (attempts >= CONFIG.MAX_POLL_ATTEMPTS) {
        showStatus('error', 'Processing timeout. Please try again.');
        resetUploadUI();
        return;
    }

    try {
        const response = await fetch(`${CONFIG.API_ENDPOINT}/results/${imageId}`);
        
        if (response.status === 404) {
            // Not ready yet, keep polling
            updateProgress(60 + (attempts * 1.5), 'Processing with AI...');
            setTimeout(() => pollForResults(imageId, attempts + 1), CONFIG.POLL_INTERVAL);
            return;
        }

        if (!response.ok) {
            throw new Error('Failed to get results');
        }

        const result = await response.json();
        
        if (result.status === 'error') {
            showStatus('error', result.results?.error || 'Processing failed');
            resetUploadUI();
            return;
        }

        // Success! Display results
        updateProgress(100, 'Complete!');
        displayResults(result);
        loadRecentResults();
        
        setTimeout(() => {
            document.getElementById('progressContainer').classList.add('d-none');
            showStatus('success', 'Image analyzed successfully!');
        }, 500);

    } catch (error) {
        console.error('Polling error:', error);
        setTimeout(() => pollForResults(imageId, attempts + 1), CONFIG.POLL_INTERVAL);
    }
}

// ============================================
// Display Results
// ============================================
function displayResults(result) {
    const container = document.getElementById('resultsContainer');
    
    if (result.results?.celebrities) {
        // Celebrity recognition results
        displayCelebrityResults(container, result);
    } else if (result.results?.labels) {
        // Image label results
        displayLabelResults(container, result);
    } else {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="bi bi-info-circle me-2"></i>
                No recognizable content found in this image.
            </div>
        `;
    }
}

function displayCelebrityResults(container, result) {
    const celebrities = result.results.celebrities || [];
    const unrecognized = result.results.unrecognizedFaces || 0;
    const processingTime = result.results.processingTime || 0;

    let html = `
        <div class="result-animate">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <span class="badge bg-success">
                    <i class="bi bi-check-circle me-1"></i>
                    ${celebrities.length} Celebrity(ies) Found
                </span>
                <small class="text-muted">
                    <i class="bi bi-clock me-1"></i>${processingTime}ms
                </small>
            </div>
    `;

    if (celebrities.length === 0) {
        html += `
            <div class="alert alert-warning">
                <i class="bi bi-person-x me-2"></i>
                No celebrities recognized in this image.
                ${unrecognized > 0 ? `<br><small>${unrecognized} unidentified face(s) detected.</small>` : ''}
            </div>
        `;
    } else {
        celebrities.forEach(celeb => {
            const confidenceClass = celeb.confidence >= 90 ? 'confidence-high' : 
                                   celeb.confidence >= 70 ? 'confidence-medium' : 'confidence-low';
            
            html += `
                <div class="card celebrity-card mb-3 result-card celebrity">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">
                            <i class="bi bi-star-fill text-warning me-2"></i>
                            ${celeb.name}
                        </h5>
                        <span class="badge ${confidenceClass} confidence-badge">
                            ${celeb.confidence.toFixed(1)}%
                        </span>
                    </div>
                    <div class="card-body">
                        ${celeb.gender && celeb.gender !== 'Unknown' ? 
                            `<p class="mb-2"><i class="bi bi-person me-2"></i>${celeb.gender}</p>` : ''}
                        ${celeb.biography ? 
                            `<p class="biography-text">${celeb.biography}</p>` : ''}
                        ${celeb.urls && celeb.urls.length > 0 ? 
                            `<a href="https://${celeb.urls[0]}" target="_blank" class="btn btn-sm btn-outline-primary mt-2">
                                <i class="bi bi-box-arrow-up-right me-1"></i>More Info
                            </a>` : ''}
                    </div>
                </div>
            `;
        });
    }

    html += '</div>';
    container.innerHTML = html;
}

function displayLabelResults(container, result) {
    const labels = result.results.labels || [];
    const processingTime = result.results.processingTime || 0;

    let html = `
        <div class="result-animate">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <span class="badge bg-primary">
                    <i class="bi bi-tags me-1"></i>
                    ${labels.length} Labels Detected
                </span>
                <small class="text-muted">
                    <i class="bi bi-clock me-1"></i>${processingTime}ms
                </small>
            </div>
    `;

    if (labels.length === 0) {
        html += `
            <div class="alert alert-warning">
                <i class="bi bi-question-circle me-2"></i>
                No labels detected with high confidence.
            </div>
        `;
    } else {
        html += '<div class="labels-container">';
        labels.forEach(label => {
            const confidenceClass = label.confidence >= 90 ? 'confidence-high' : 
                                   label.confidence >= 70 ? 'confidence-medium' : 'confidence-low';
            
            html += `
                <span class="label-pill">
                    ${label.name}
                    <span class="badge ${confidenceClass} ms-1 confidence">${label.confidence.toFixed(0)}%</span>
                </span>
            `;
        });
        html += '</div>';
    }

    html += '</div>';
    container.innerHTML = html;
}

// ============================================
// Recent Results
// ============================================
async function loadRecentResults() {
    const container = document.getElementById('recentResults');
    
    try {
        const response = await fetch(`${CONFIG.API_ENDPOINT}/results`);
        
        if (!response.ok) {
            throw new Error('Failed to load results');
        }

        const data = await response.json();
        const results = data.results || [];

        if (results.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-inbox display-4"></i>
                    <p class="mt-2">No recent analyses yet. Upload an image to get started!</p>
                </div>
            `;
            return;
        }

        let html = '<div class="row g-3">';
        
        results.slice(0, 12).forEach(result => {
            const statusIcon = result.status === 'success' ? 'check-circle text-success' :
                              result.status === 'error' ? 'x-circle text-danger' : 'question-circle text-warning';
            
            const itemCount = result.results?.celebrities?.length || result.results?.labels?.length || 0;
            const itemType = result.results?.celebrities ? 'celebrities' : 'labels';
            
            html += `
                <div class="col-6 col-md-4 col-lg-3">
                    <div class="card recent-item h-100 position-relative">
                        <button class="btn btn-sm btn-danger delete-btn position-absolute" 
                                onclick="deleteResult('${result.imageId}', event)" 
                                title="Delete">
                            <i class="bi bi-trash"></i>
                        </button>
                        <div onclick="viewResult('${result.imageId}')" style="cursor: pointer;">
                            ${result.imageUrl ? 
                                `<img src="${result.imageUrl}" class="card-img-top" alt="${result.filename}">` :
                                `<div class="card-img-top bg-secondary d-flex align-items-center justify-content-center" style="height:120px">
                                    <i class="bi bi-image text-white display-6"></i>
                                </div>`
                            }
                            <div class="card-body p-2">
                                <p class="card-text small mb-1 text-truncate">${result.filename}</p>
                                <div class="d-flex justify-content-between align-items-center">
                                    <small class="text-muted">${itemCount} ${itemType}</small>
                                    <i class="bi bi-${statusIcon}"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading recent results:', error);
        container.innerHTML = `
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle me-2"></i>
                Unable to load recent results. <a href="#" onclick="loadRecentResults(); return false;">Retry</a>
            </div>
        `;
    }
}

async function viewResult(imageId) {
    try {
        const response = await fetch(`${CONFIG.API_ENDPOINT}/results/${imageId}`);
        if (response.ok) {
            const result = await response.json();
            displayResults(result);
            
            // Scroll to results
            document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
        }
    } catch (error) {
        console.error('Error viewing result:', error);
    }
}

// ============================================
// UI Helpers
// ============================================
function setupRefreshButton() {
    document.getElementById('refreshBtn').addEventListener('click', () => {
        loadRecentResults();
    });
}

function showStatus(type, message) {
    const statusDiv = document.getElementById('statusMessage');
    const className = type === 'success' ? 'status-success' : 
                     type === 'error' ? 'status-error' : 'status-processing';
    const icon = type === 'success' ? 'check-circle' : 
                type === 'error' ? 'x-circle' : 'hourglass-split';
    
    statusDiv.className = `alert ${className} mt-3`;
    statusDiv.innerHTML = `<i class="bi bi-${icon} me-2"></i>${message}`;
    statusDiv.classList.remove('d-none');
}

function hideStatus() {
    document.getElementById('statusMessage').classList.add('d-none');
}

function resetUploadUI() {
    document.getElementById('uploadBtn').disabled = false;
    document.getElementById('progressContainer').classList.add('d-none');
}

// Make viewResult available globally
window.viewResult = viewResult;

// ============================================
// Delete Functionality
// ============================================
async function deleteResult(imageId, event) {
    event.stopPropagation(); // Prevent triggering viewResult
    
    if (!confirm('Are you sure you want to delete this result?')) {
        return;
    }
    
    try {
        const response = await fetch(`${CONFIG.API_ENDPOINT}/results/${imageId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete result');
        }
        
        // Refresh the results list
        loadRecentResults();
        
        // Clear the results display if we deleted the currently viewed result
        if (currentImageId === imageId) {
            document.getElementById('resultsContainer').innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-inbox display-1"></i>
                    <p class="mt-3">Upload an image to see AI recognition results</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Delete error:', error);
        alert('Failed to delete result. Please try again.');
    }
}

// Make deleteResult available globally
window.deleteResult = deleteResult;
