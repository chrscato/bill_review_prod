/**
 * Main JavaScript functionality for the OCR Corrections tool
 */

let currentFileName = null;
let currentData = null;
let originalData = null;
let files = [];
let currentFileIndex = 0;

document.addEventListener('DOMContentLoaded', function() {
    loadFiles();
    debugPaths();
    
    // Add event listeners
    document.getElementById('debugBtn').addEventListener('click', debugPaths);
    document.getElementById('openPdfBtn').addEventListener('click', openPDF);
    document.getElementById('addLineBtn').addEventListener('click', addLineItem);
    document.getElementById('prevButton').addEventListener('click', loadPrevious);
    document.getElementById('nextButton').addEventListener('click', loadNext);
    document.getElementById('saveButton').addEventListener('click', saveChanges);
});

/**
 * Load the list of files needing correction
 */
async function loadFiles() {
    try {
        console.log('Loading files from /mapping/api/corrections/files');
        const response = await fetch('/mapping/api/corrections/files');
        const data = await response.json();
        console.log('API Response:', data);
        
        const fileList = document.getElementById('fileList');
        fileList.innerHTML = '';

        if (data.files && data.files.length > 0) {
            files = data.files;
            data.files.forEach(file => {
                const listItem = document.createElement('a');
                listItem.className = 'list-group-item list-group-item-action';
                listItem.textContent = file;
                listItem.href = '#';
                listItem.onclick = (e) => {
                    e.preventDefault();
                    loadFile(file);
                };
                fileList.appendChild(listItem);
            });
            
            // Enable navigation buttons
            document.getElementById('prevButton').disabled = false;
            document.getElementById('nextButton').disabled = false;
            
            // Load the first file
            if (files.length > 0) {
                loadFile(files[0]);
            }
        } else {
            fileList.innerHTML = '<div class="list-group-item">No files need correction</div>';
            document.getElementById('prevButton').disabled = true;
            document.getElementById('nextButton').disabled = true;
        }
    } catch (error) {
        console.error('Error loading files:', error);
        const fileList = document.getElementById('fileList');
        fileList.innerHTML = '<div class="list-group-item text-danger">Error loading files</div>';
    }
}

/**
 * Load a specific file and display its content
 * @param {string} filename - Name of the file to load
 */
async function loadFile(filename) {
    try {
        // Update UI to show loading state
        document.getElementById('recordDetails').innerHTML = '<div class="alert alert-info">Loading file data...</div>';
        
        // Fetch the file data
        const response = await fetch(`/mapping/api/corrections/file/${filename}`);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to load file');
        }
        
        // Store current data
        currentFileName = filename;
        currentData = result.data;
        originalData = JSON.parse(JSON.stringify(result.data)); // Deep copy for comparison
        
        // Update record details display
        displayData();
        
        // Load the PDF
        loadPDF(filename);
        
        // Enable the save button
        document.getElementById('saveButton').disabled = false;
        
        // Update the current file index
        currentFileIndex = files.indexOf(filename);
        
        // Update navigation buttons
        updateNavigationButtons();
        
        // Highlight the selected file in the list
        const fileItems = document.querySelectorAll('#fileList a');
        fileItems.forEach(item => {
            if (item.textContent === filename) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    } catch (error) {
        console.error('Error loading file:', error);
        document.getElementById('recordDetails').innerHTML = 
            `<div class="alert alert-danger">Error loading file: ${error.message}</div>`;
    }
}

/**
 * Display the current data in the editor interface
 */
function displayData() {
    const content = document.getElementById('recordDetails');
    content.innerHTML = '';

    if (!currentData) {
        content.innerHTML = '<div class="alert alert-info">No data to display</div>';
        return;
    }

    // Update form fields
    document.getElementById('patientName').value = currentData.patient_info?.patient_name || '';
    document.getElementById('patientDOB').value = currentData.patient_info?.patient_dob || '';
    document.getElementById('patientZip').value = currentData.patient_info?.patient_zip || '';
    
    // Display service lines
    const serviceLines = document.getElementById('serviceLines');
    serviceLines.innerHTML = '';
    
    if (currentData.service_lines && currentData.service_lines.length > 0) {
        currentData.service_lines.forEach((line, index) => {
            const lineElement = document.createElement('div');
            lineElement.className = 'service-line';
            lineElement.innerHTML = `
                <div class="service-line-header">
                    <h5 class="service-line-title">Service Line ${index + 1}</h5>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <label class="form-label">Date of Service</label>
                        <input type="text" class="form-control" 
                               value="${line.date_of_service || ''}"
                               onchange="updateServiceLine(${index}, 'date_of_service', this.value)">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">CPT Code</label>
                        <input type="text" class="form-control"
                               value="${line.cpt_code || ''}"
                               onchange="updateServiceLine(${index}, 'cpt_code', this.value)">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Units</label>
                        <input type="number" class="form-control"
                               value="${line.units || 1}"
                               onchange="updateServiceLine(${index}, 'units', parseInt(this.value))">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Charge Amount</label>
                        <input type="text" class="form-control"
                               value="${line.charge_amount || ''}"
                               onchange="updateServiceLine(${index}, 'charge_amount', this.value)">
                    </div>
                </div>
            `;
            serviceLines.appendChild(lineElement);
        });
    } else {
        serviceLines.innerHTML = '<div class="alert alert-info">No service lines found</div>';
    }
}

/**
 * Update a service line field
 * @param {number} index - Index of the service line
 * @param {string} field - Field to update
 * @param {*} value - New value
 */
function updateServiceLine(index, field, value) {
    if (!currentData.service_lines) {
        currentData.service_lines = [];
    }
    
    if (!currentData.service_lines[index]) {
        currentData.service_lines[index] = {};
    }
    
    currentData.service_lines[index][field] = value;
}

/**
 * Load the PDF into the viewer
 * @param {string} filename - Name of the file to load
 */
function loadPDF(filename) {
    // Get the PDF URL
    const pdfUrl = `/mapping/api/corrections/pdf/${filename}`;
    
    // Load the full PDF
    document.getElementById('pdfFrame').src = pdfUrl;
    
    // Load the header region
    document.querySelector('#headerRegion .pdf-region iframe').src = pdfUrl;
    
    // Load the service lines region
    document.querySelector('#serviceRegion .pdf-region iframe').src = pdfUrl;
}

/**
 * Update navigation buttons state
 */
function updateNavigationButtons() {
    const prevButton = document.getElementById('prevButton');
    const nextButton = document.getElementById('nextButton');
    
    prevButton.disabled = currentFileIndex <= 0;
    nextButton.disabled = currentFileIndex >= files.length - 1;
}

/**
 * Load the previous file
 */
function loadPrevious() {
    if (currentFileIndex > 0) {
        currentFileIndex--;
        loadFile(files[currentFileIndex]);
    }
}

/**
 * Load the next file
 */
function loadNext() {
    if (currentFileIndex < files.length - 1) {
        currentFileIndex++;
        loadFile(files[currentFileIndex]);
    }
}

/**
 * Save changes to the current file
 */
async function saveChanges() {
    if (!currentFileName || !currentData) {
        alert('No file loaded');
        return;
    }
    
    try {
        const response = await fetch('/mapping/api/corrections/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                filename: currentFileName,
                content: currentData,
                original_content: originalData
            }),
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Save failed');
        }
        
        alert('Changes saved successfully');
        
        // Update the files list
        files.splice(currentFileIndex, 1);
        
        if (files.length === 0) {
            // No more files
            currentData = null;
            currentFileIndex = 0;
            displayData();
            updateNavigationButtons();
        } else {
            // Adjust current index if needed
            if (currentFileIndex >= files.length) {
                currentFileIndex = files.length - 1;
            }
            
            // Load the next file
            loadFile(files[currentFileIndex]);
        }
    } catch (error) {
        console.error('Save error:', error);
        alert(`Error saving changes: ${error.message}`);
    }
}

/**
 * Open the full PDF in a new window
 */
function openPDF() {
    if (!currentData) return;
    window.open(`/mapping/api/corrections/pdf/${files[currentFileIndex]}`, '_blank');
}

/**
 * Add a new line item
 */
function addLineItem() {
    if (!currentData) return;
    
    if (!currentData.service_lines) {
        currentData.service_lines = [];
    }
    
    currentData.service_lines.push({
        cpt_code: '',
        units: ''
    });
    
    displayData();
}

/**
 * Remove a line item
 * @param {number} index - Index of line item to remove
 */
function removeLineItem(index) {
    if (!currentData || !currentData.service_lines) return;
    
    currentData.service_lines.splice(index, 1);
    displayData();
}

/**
 * Update a field in the current data
 * @param {string} field - Field name to update
 * @param {string} value - New value
 */
function updateField(field, value) {
    if (!currentData) return;
    currentData[field] = value;
}

/**
 * Update a line item field
 * @param {number} index - Index of line item
 * @param {string} field - Field name to update
 * @param {string} value - New value
 */
function updateLineItem(index, field, value) {
    if (!currentData || !currentData.service_lines) return;
    
    if (field === 'units') {
        value = parseInt(value) || 0;
    }
    
    currentData.service_lines[index][field] = value;
}

/**
 * Update the file info display
 */
function updateFileInfo() {
    const fileInfo = document.getElementById('fileInfo');
    const remaining = files.length - currentFileIndex - 1;
    
    if (files.length === 0) {
        fileInfo.innerHTML = 'No files to correct';
    } else {
        fileInfo.innerHTML = `
            <strong>${remaining}</strong> file${remaining !== 1 ? 's' : ''} remaining
            <br>
            <small>Current: ${files[currentFileIndex]}</small>
        `;
    }
}

/**
 * Debug function to show file paths
 */
async function debugPaths() {
    try {
        const response = await fetch('/mapping/api/corrections/debug');
        const data = await response.json();
        
        console.log('Debug paths:', data);
        showAlert('Debug paths logged to console', 'info');
    } catch (error) {
        console.error('Error getting debug paths:', error);
        showAlert('Error getting debug paths', 'danger');
    }
}

/**
 * Show an alert message
 * @param {string} message - Message to display
 * @param {string} type - Alert type (success, danger, etc.)
 * @param {number} duration - Duration in milliseconds
 */
function showAlert(message, type = 'success', duration = 3000) {
    const alertContainer = document.getElementById('alertContainer');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertContainer.appendChild(alert);
    
    setTimeout(() => {
        alert.remove();
    }, duration);
} 