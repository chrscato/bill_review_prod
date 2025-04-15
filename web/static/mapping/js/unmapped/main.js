// Global variables
let currentFile = null;
let currentFileContent = null;

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    loadFileList();
    setupEventListeners();
});

// Load the list of unmapped files
function loadFileList() {
    fetch('/mapping/api/files')
        .then(response => response.json())
        .then(data => {
            const fileList = document.getElementById('fileList');
            fileList.innerHTML = '';
            
            data.files.forEach(file => {
                const item = document.createElement('a');
                item.href = '#';
                item.className = 'list-group-item list-group-item-action';
                item.textContent = file;
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    selectFile(file);
                });
                fileList.appendChild(item);
            });
        })
        .catch(error => {
            console.error('Error loading file list:', error);
            showAlert('Error loading file list', 'danger');
        });
}

// Select a file and load its content
function selectFile(filename) {
    currentFile = filename;
    
    // Update UI
    document.querySelectorAll('#fileList .list-group-item').forEach(item => {
        item.classList.remove('active');
        if (item.textContent === filename) {
            item.classList.add('active');
        }
    });
    
    // Load file content
    fetch(`/mapping/api/file/${filename}`)
        .then(response => response.json())
        .then(data => {
            currentFileContent = data.data;
            displayFileContent(data.data);
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
}

// Display file content in the record details section
function displayFileContent(content) {
    const recordDetails = document.getElementById('recordDetails');
    
    // Clear previous content
    recordDetails.innerHTML = '';
    
    // Add patient info
    const patientInfo = document.createElement('div');
    patientInfo.className = 'mb-3';
    patientInfo.innerHTML = `
        <h5>Patient Information</h5>
        <p><strong>Name:</strong> ${content.patient_info?.patient_name || 'N/A'}</p>
        <p><strong>DOB:</strong> ${content.patient_info?.date_of_birth || 'N/A'}</p>
        <p><strong>Member ID:</strong> ${content.patient_info?.member_id || 'N/A'}</p>
    `;
    recordDetails.appendChild(patientInfo);
    
    // Add service lines
    const serviceLines = document.createElement('div');
    serviceLines.className = 'mb-3';
    serviceLines.innerHTML = `
        <h5>Service Lines</h5>
        <div class="table-responsive">
            <table class="table table-sm">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>CPT</th>
                        <th>Description</th>
                        <th>Charges</th>
                    </tr>
                </thead>
                <tbody>
                    ${content.service_lines?.map(line => `
                        <tr>
                            <td>${line.date_of_service || 'N/A'}</td>
                            <td>${line.cpt_code || 'N/A'}</td>
                            <td>${line.description || 'N/A'}</td>
                            <td>${line.charges || 'N/A'}</td>
                        </tr>
                    `).join('') || '<tr><td colspan="4">No service lines</td></tr>'}
                </tbody>
            </table>
        </div>
    `;
    recordDetails.appendChild(serviceLines);
}

// Load PDF regions
function loadPdfRegions(filename) {
    // Load header region
    fetch(`/mapping/api/pdf_region/${filename}/header`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('headerImage').src = `data:image/png;base64,${data.image}`;
        })
        .catch(error => console.error('Error loading header region:', error));
    
    // Load service lines region
    fetch(`/mapping/api/pdf_region/${filename}/service_lines`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('serviceImage').src = `data:image/png;base64,${data.image}`;
        })
        .catch(error => console.error('Error loading service lines region:', error));
}

// Enable/disable buttons based on file selection
function enableButtons() {
    const buttons = ['saveButton', 'escalateButton', 'notFoundButton'];
    buttons.forEach(buttonId => {
        document.getElementById(buttonId).disabled = !currentFile;
    });
}

// Setup event listeners
function setupEventListeners() {
    // Save button
    document.getElementById('saveButton').addEventListener('click', () => {
        if (!currentFile || !currentFileContent) return;
        
        const orderId = document.getElementById('orderIdInput').value;
        const filemakerId = document.getElementById('filemakerInput').value;
        
        if (!orderId || !filemakerId) {
            showAlert('Please enter both Order ID and FileMaker Record Number', 'warning');
            return;
        }
        
        currentFileContent.order_id = orderId;
        currentFileContent.filemaker_id = filemakerId;
        
        fetch('/mapping/api/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filename: currentFile,
                content: currentFileContent
            })
        })
        .then(response => response.json())
        .then(data => {
            showAlert('File saved successfully', 'success');
            loadFileList();
            currentFile = null;
            currentFileContent = null;
            enableButtons();
        })
        .catch(error => {
            console.error('Error saving file:', error);
            showAlert('Error saving file', 'danger');
        });
    });
    
    // Escalate button
    document.getElementById('escalateButton').addEventListener('click', () => {
        document.getElementById('escalationForm').classList.remove('d-none');
    });
    
    // Submit escalation
    document.getElementById('submitEscalation').addEventListener('click', () => {
        const notes = document.getElementById('escalationNotes').value;
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
                content: currentFileContent,
                notes: notes
            })
        })
        .then(response => response.json())
        .then(data => {
            showAlert('File escalated successfully', 'success');
            loadFileList();
            currentFile = null;
            currentFileContent = null;
            enableButtons();
            document.getElementById('escalationForm').classList.add('d-none');
            document.getElementById('escalationNotes').value = '';
        })
        .catch(error => {
            console.error('Error escalating file:', error);
            showAlert('Error escalating file', 'danger');
        });
    });
    
    // Cancel escalation
    document.getElementById('cancelEscalation').addEventListener('click', () => {
        document.getElementById('escalationForm').classList.add('d-none');
        document.getElementById('escalationNotes').value = '';
    });
    
    // Not found button
    document.getElementById('notFoundButton').addEventListener('click', () => {
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
            showAlert('File marked as not found', 'success');
            loadFileList();
            currentFile = null;
            currentFileContent = null;
            enableButtons();
        })
        .catch(error => {
            console.error('Error marking file as not found:', error);
            showAlert('Error marking file as not found', 'danger');
        });
    });
}

// Show alert message
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Remove alert after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
} 