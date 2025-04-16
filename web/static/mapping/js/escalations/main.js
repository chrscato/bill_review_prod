// Create a namespace for escalations
const Escalations = {
    currentFile: null,
    currentFileContent: null,
    files: [],

    // Initialize the page
    init: function() {
        this.loadFiles();
        this.setupEventListeners();
    },

    // Load the list of files
    loadFiles: async function() {
        try {
            const response = await fetch('/mapping/api/escalations/files');
            const data = await response.json();
            this.files = data.files || [];
            this.updateFileList();
        } catch (error) {
            console.error('Error loading files:', error);
            this.showAlert('Error loading files', 'danger');
        }
    },

    // Update the file list in the UI
    updateFileList: function() {
        const fileList = document.getElementById('fileList');
        fileList.innerHTML = '';
        
        this.files.forEach(file => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action';
            item.textContent = file;
            item.addEventListener('click', () => this.selectFile(file));
            fileList.appendChild(item);
        });
    },

    // Select a file and load its content
    selectFile: async function(filename) {
        try {
            this.currentFile = filename;
            const response = await fetch(`/mapping/api/escalations/file/${filename}`);
            if (!response.ok) {
                throw new Error(`Failed to load file: ${response.statusText}`);
            }
            
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }
            
            this.currentFileContent = data.data;
            this.displayData();
            this.loadPDF(filename);
            this.enableButtons();
        } catch (error) {
            console.error('Error loading file:', error);
            this.showAlert('Error loading file: ' + error.message, 'danger');
            this.currentFile = null;
            this.currentFileContent = null;
            this.enableButtons();
        }
    },

    // Save changes
    saveChanges: async function() {
        if (!this.currentFile) {
            this.showAlert('No file selected', 'warning');
            return;
        }

        try {
            const response = await fetch('/mapping/api/escalations/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filename: this.currentFile,
                    content: this.currentFileContent
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to save changes: ${response.statusText}`);
            }

            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }

            this.showAlert('Changes saved successfully', 'success');
            this.loadFiles();
        } catch (error) {
            console.error('Error saving changes:', error);
            this.showAlert('Error saving changes: ' + error.message, 'danger');
        }
    },

    // Load PDF
    loadPDF: function(filename) {
        const pdfFrame = document.getElementById('pdfFrame');
        if (pdfFrame) {
            pdfFrame.src = `/mapping/api/escalations/pdf/${filename}`;
        }
        
        this.loadPdfRegions(filename);
    },

    // Load PDF regions
    loadPdfRegions: async function(filename) {
        try {
            // Load header region
            const headerResponse = await fetch(`/mapping/api/escalations/pdf_region/${filename}/header`);
            if (headerResponse.ok) {
                const headerData = await headerResponse.json();
                if (headerData.image) {
                    const headerImg = document.createElement('img');
                    headerImg.src = headerData.image;
                    headerImg.style.maxWidth = '100%';
                    document.getElementById('headerRegion').innerHTML = '';
                    document.getElementById('headerRegion').appendChild(headerImg);
                }
            }

            // Load service lines region
            const serviceLinesResponse = await fetch(`/mapping/api/escalations/pdf_region/${filename}/service_lines`);
            if (serviceLinesResponse.ok) {
                const serviceLinesData = await serviceLinesResponse.json();
                if (serviceLinesData.image) {
                    const serviceLinesImg = document.createElement('img');
                    serviceLinesImg.src = serviceLinesData.image;
                    serviceLinesImg.style.maxWidth = '100%';
                    document.getElementById('serviceLinesRegion').innerHTML = '';
                    document.getElementById('serviceLinesRegion').appendChild(serviceLinesImg);
                }
            }
        } catch (error) {
            console.error('Error loading PDF regions:', error);
            this.showAlert('Error loading PDF regions', 'danger');
        }
    },

    // Show alert
    showAlert: function(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        const alertContainer = document.getElementById('alertContainer');
        if (alertContainer) {
            alertContainer.appendChild(alertDiv);
            setTimeout(() => alertDiv.remove(), 5000);
        }
    },

    // Enable/disable buttons based on file selection
    enableButtons: function() {
        const hasFile = this.currentFile !== null;
        document.getElementById('saveButton').disabled = !hasFile;
        document.getElementById('escalateButton').disabled = !hasFile;
        document.getElementById('denyButton').disabled = !hasFile;
    },

    // Setup event listeners
    setupEventListeners: function() {
        const saveButton = document.getElementById('saveButton');
        if (saveButton) {
            saveButton.addEventListener('click', () => this.saveChanges());
        }
        
        const escalateButton = document.getElementById('escalateButton');
        if (escalateButton) {
            escalateButton.addEventListener('click', () => this.escalate());
        }

        const denyButton = document.getElementById('denyButton');
        if (denyButton) {
            denyButton.addEventListener('click', () => this.showDenialModal());
        }

        const confirmDenialButton = document.getElementById('confirmDenial');
        if (confirmDenialButton) {
            confirmDenialButton.addEventListener('click', () => this.processDenial());
        }
    },

    // Show the denial modal
    showDenialModal: function() {
        const modal = new bootstrap.Modal(document.getElementById('denialModal'));
        modal.show();
    },

    // Process the denial
    processDenial: async function() {
        const denialReason = document.getElementById('denialReason').value;
        if (!denialReason) {
            this.showAlert('Please select a denial reason', 'warning');
            return;
        }

        if (!this.currentFile) {
            this.showAlert('No file selected', 'warning');
            return;
        }

        try {
            // Add denial reason to the JSON
            this.currentFileContent.denial_reason = denialReason;

            const response = await fetch('/mapping/api/escalations/deny', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filename: this.currentFile,
                    content: this.currentFileContent
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to process denial: ${response.statusText}`);
            }

            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }

            this.showAlert('Bill denied successfully', 'success');
            
            // Close the modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('denialModal'));
            modal.hide();
            
            // Refresh the file list
            this.loadFiles();
        } catch (error) {
            console.error('Error processing denial:', error);
            this.showAlert('Error processing denial: ' + error.message, 'danger');
        }
    }
};

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    Escalations.init();
}); 