// Global variables
let currentFile = null;
let currentFileContent = null;
let currentFileIndex = -1;
let files = [];

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    loadFileList();
    setupEventListeners();
    debugPaths();
});

// Load the list of unmapped files
function loadFileList() {
    console.log('=== Starting loadFileList ===');
    console.log('Making request to /mapping/api/files');
    
    fetch('/mapping/api/files')
        .then(response => {
            console.log('Response received:', response);
            console.log('Response status:', response.status);
            console.log('Response headers:', Object.fromEntries(response.headers.entries()));
            return response.json();
        })
        .then(data => {
            console.log('API response data:', data);
            files = data.files || [];
            const fileList = document.getElementById('fileList');
            fileList.innerHTML = '';
            
            if (files.length > 0) {
                console.log(`Found ${files.length} files:`, files);
                files.forEach((file, index) => {
                    const item = document.createElement('a');
                    item.href = '#';
                    item.className = 'list-group-item list-group-item-action';
                    item.textContent = file;
                    item.addEventListener('click', (e) => {
                        e.preventDefault();
                        selectFile(file, index);
                    });
                    fileList.appendChild(item);
                });
                
                // Select the first file
                selectFile(files[0], 0);
            } else {
                console.log('No files found in response');
                fileList.innerHTML = '<div class="list-group-item">No unmapped files found</div>';
            }
            
            updateNavigationButtons();
        })
        .catch(error => {
            console.error('Error in loadFileList:', error);
            showAlert('Error loading file list', 'danger');
        });
}

// Select a file and load its content
function selectFile(filename, index) {
    currentFile = filename;
    currentFileIndex = index;
    
    // Update UI
    document.querySelectorAll('#fileList .list-group-item').forEach(item => {
        item.classList.remove('active');
        if (item.textContent === filename) {
            item.classList.add('active');
        }
    });
    
    // Update file info
    document.getElementById('fileInfo').textContent = `File ${index + 1} of ${files.length}: ${filename}`;
    
    // Load file content
    fetch(`/mapping/api/file/${filename}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            currentFileContent = data.data;
            
            // Initialize editors
            initializePatientEditor(data.data);
            initializeServiceLineEditor(data.data);
            
            enableButtons();
        })
        .catch(error => {
            console.error('Error loading file:', error);
            showAlert('Error loading file', 'danger');
        });
    
    // Load PDF
    document.getElementById('pdfFrame').src = `/mapping/api/pdf/${filename}`;
    
    // Load PDF regions
    loadPdfRegions(filename);
    
    // Update navigation buttons
    updateNavigationButtons();
}

// Load PDF regions
async function loadPdfRegions(filename) {
    try {
        // Load header region
        const headerResponse = await fetch(`/mapping/api/pdf_region/${filename}/header`);
        if (headerResponse.ok) {
            const headerData = await headerResponse.json();
            if (headerData.image) {
                const headerImg = document.createElement('img');
                headerImg.src = headerData.image;
                headerImg.style.maxWidth = '100%';
                document.getElementById('headerRegion').innerHTML = '';
                document.getElementById('headerRegion').appendChild(headerImg);
            }
        } else {
            console.error('Failed to load header region:', await headerResponse.text());
        }

        // Load service lines region
        const serviceLinesResponse = await fetch(`/mapping/api/pdf_region/${filename}/service_lines`);
        if (serviceLinesResponse.ok) {
            const serviceLinesData = await serviceLinesResponse.json();
            if (serviceLinesData.image) {
                const serviceLinesImg = document.createElement('img');
                serviceLinesImg.src = serviceLinesData.image;
                serviceLinesImg.style.maxWidth = '100%';
                document.getElementById('serviceLinesRegion').innerHTML = '';
                document.getElementById('serviceLinesRegion').appendChild(serviceLinesImg);
            }
        } else {
            console.error('Failed to load service lines region:', await serviceLinesResponse.text());
        }
    } catch (error) {
        console.error('Error loading PDF regions:', error);
        showAlert('Error loading PDF regions', 'danger');
    }
}

// Show PDF link when region extraction fails
function showPDFLink(region, filename) {
    const container = document.getElementById(`${region}Image`);
    container.innerHTML = `
        <div class="alert alert-warning">
            <p>Could not extract ${region} region. <a href="/mapping/api/pdf/${filename}" target="_blank">View full PDF</a></p>
        </div>
    `;
}

// Update navigation buttons
function updateNavigationButtons() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    
    prevBtn.disabled = currentFileIndex <= 0;
    nextBtn.disabled = currentFileIndex >= files.length - 1;
}

// Navigation functions
function loadPrevious() {
    if (currentFileIndex > 0) {
        selectFile(files[currentFileIndex - 1], currentFileIndex - 1);
    }
}

function loadNext() {
    if (currentFileIndex < files.length - 1) {
        selectFile(files[currentFileIndex + 1], currentFileIndex + 1);
    }
}

// Enable/disable buttons based on file selection
function enableButtons() {
    const hasFile = currentFile !== null;
    document.getElementById('saveButton').disabled = !hasFile;
    document.getElementById('notFoundButton').disabled = !hasFile;
    document.getElementById('escalateButton').disabled = !hasFile;
}

// Save changes
function saveChanges() {
    if (!currentFile || !currentFileContent) return;
    
    // Update service lines from editor
    currentFileContent.service_lines = getServiceLines();
    
    fetch('/mapping/api/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filename: currentFile,
            data: currentFileContent
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        showAlert('Changes saved successfully', 'success');
        document.getElementById('saveButton').disabled = true;
    })
    .catch(error => {
        console.error('Error saving changes:', error);
        showAlert('Error saving changes', 'danger');
    });
}

// Mark file as not found
function markAsNotFound() {
    if (!currentFile) return;
    
    fetch('/mapping/api/not_found', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filename: currentFile
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        showAlert('File marked as not found', 'success');
        loadFileList(); // Reload file list
    })
    .catch(error => {
        console.error('Error marking file as not found:', error);
        showAlert('Error marking file as not found', 'danger');
    });
}

// Escalate file
function escalate() {
    if (!currentFile) return;
    
    const notes = document.getElementById('escalationNotes').value.trim();
    if (!notes) {
        showAlert('Please enter escalation notes', 'warning');
        return;
    }
    
    fetch('/mapping/api/escalate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filename: currentFile,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        showAlert('File escalated successfully', 'success');
        document.getElementById('escalationForm').classList.add('d-none');
        document.getElementById('escalationNotes').value = '';
        loadFileList(); // Reload file list
    })
    .catch(error => {
        console.error('Error escalating file:', error);
        showAlert('Error escalating file', 'danger');
    });
}

// Debug paths
function debugPaths() {
    fetch('/mapping/api/debug_paths')
        .then(response => response.json())
        .then(data => {
            console.log('Debug paths:', data);
        })
        .catch(error => {
            console.error('Error getting debug paths:', error);
        });
}

// Show alert
function showAlert(message, type = 'success', duration = 3000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const alertContainer = document.getElementById('alertContainer');
    alertContainer.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, duration);
}

// Setup event listeners
function setupEventListeners() {
    // Navigation buttons
    document.getElementById('prevBtn').addEventListener('click', loadPrevious);
    document.getElementById('nextBtn').addEventListener('click', loadNext);
    
    // Action buttons
    document.getElementById('saveButton').addEventListener('click', saveChanges);
    document.getElementById('notFoundButton').addEventListener('click', markAsNotFound);
    document.getElementById('escalateButton').addEventListener('click', () => {
        document.getElementById('escalationForm').classList.remove('d-none');
    });
    document.getElementById('submitEscalation').addEventListener('click', escalate);
    document.getElementById('cancelEscalation').addEventListener('click', () => {
        document.getElementById('escalationForm').classList.add('d-none');
        document.getElementById('escalationNotes').value = '';
    });
} 