// Global variables
let currentDocument = null;
let allDocuments = [];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadFailures();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            filterDocuments(e.target.value);
        });
    }

    // Status filter
    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
        statusFilter.addEventListener('change', function(e) {
            filterDocuments(document.getElementById('searchInput').value, e.target.value);
        });
    }

    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadFailures);
    }
}

// Load validation failures
async function loadFailures() {
    showLoading();
    try {
        const response = await fetch('/api/failures');
        const result = await response.json();
        if (result.status === 'success') {
            allDocuments = result.data;
            renderDocumentList(result.data);
        } else {
            showError('Failed to load validation failures: ' + result.message);
        }
    } catch (error) {
        console.error('Error loading failures:', error);
        showError('Failed to load validation failures');
    } finally {
        hideLoading();
    }
}

// Render document list
function renderDocumentList(documents) {
    const container = document.getElementById('documentList');
    container.innerHTML = '';

    documents.forEach(doc => {
        const div = document.createElement('div');
        div.className = 'document-item';
        div.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>${doc.filename}</strong>
                    <div class="text-muted small">Order ID: ${doc.order_id || 'N/A'}</div>
                </div>
                <span class="status-badge ${doc.status === 'critical' ? 'status-critical' : 'status-non-critical'}">
                    ${doc.status}
                </span>
            </div>
            <div class="text-muted small mt-1">
                Patient: ${doc.patient_name || 'N/A'} | Date: ${doc.date_of_service || 'N/A'}
            </div>
        `;
        div.onclick = () => selectDocument(doc);
        container.appendChild(div);
    });
}

// Select a document
async function selectDocument(doc) {
    currentDocument = doc;
    
    // Update active state in document list
    document.querySelectorAll('.document-item').forEach(item => {
        item.classList.remove('active');
    });
    event.currentTarget.classList.add('active');

    // Load and display details
    showLoading();
    try {
        // Fetch JSON details first
        const jsonResponse = await fetch(`/api/failures/${doc.filename}`);
        const jsonData = await jsonResponse.json();
        
        if (jsonData.status !== 'success') {
            throw new Error(`Failed to load JSON details: ${jsonData.message}`);
        }
        
        // Then try to fetch DB details
        let dbData = null;
        try {
            const dbResponse = await fetch(`/api/order/${doc.order_id}`);
            dbData = await dbResponse.json();
            
            if (dbData.status !== 'success') {
                console.warn(`Database details not available: ${dbData.message}`);
            }
        } catch (dbError) {
            console.warn('Failed to load database details:', dbError);
        }
        
        // Display details even if DB data is missing
        displayDetails(jsonData.data, dbData?.data || null);
        
    } catch (error) {
        console.error('Error loading document details:', error);
        showError(`Failed to load document details: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// Display document details
function displayDetails(jsonDetails, dbDetails) {
    if (!jsonDetails) {
        showError('No document details available');
        return;
    }
    
    // Store the current document data for later use
    window.currentDocumentData = jsonDetails;
    
    // Display HCFA details
    const hcfaDetails = document.getElementById('hcfaDetails');
    if (!hcfaDetails) return;

    // Format DOB to remove newlines and extra spaces
    const formatDOB = (dob) => {
        if (!dob) return 'N/A';
        return dob.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
    };

    // Helper function to create editable field
    const createEditableField = (value, field, section, index = null) => {
        const displayValue = value || 'N/A';
        const inputValue = value || '';
        const dataAttr = index !== null ? `data-index="${index}"` : '';
        
        return `
            <div class="editable-field">
                <span class="editable-display" style="display: block;">${displayValue}</span>
                <input type="text" 
                       class="form-control form-control-sm editable-input" 
                       value="${inputValue}"
                       data-field="${field}"
                       data-section="${section}"
                       ${dataAttr}
                       style="display: none; width: 100%;">
            </div>
        `;
    };

    hcfaDetails.innerHTML = `
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">Patient Information</h6>
                <button class="btn btn-primary btn-sm save-section" data-section="patient_info" style="display: none;">Save Changes</button>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <tr>
                            <th>Name</th>
                            <td>${createEditableField(jsonDetails.patient_info?.patient_name, 'patient_name', 'patient_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="patient_name" data-section="patient_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>DOB</th>
                            <td>${createEditableField(formatDOB(jsonDetails.patient_info?.patient_dob), 'patient_dob', 'patient_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="patient_dob" data-section="patient_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Zip Code</th>
                            <td>${createEditableField(jsonDetails.patient_info?.patient_zip, 'patient_zip', 'patient_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="patient_zip" data-section="patient_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">Billing Information</h6>
                <button class="btn btn-primary btn-sm save-section" data-section="billing_info" style="display: none;">Save Changes</button>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <tr>
                            <th>Order ID</th>
                            <td>${jsonDetails.Order_ID || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>FileMaker Number</th>
                            <td>${createEditableField(jsonDetails.filemaker_number, 'filemaker_number', 'root')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="filemaker_number" data-section="root">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Provider Name</th>
                            <td>${createEditableField(jsonDetails.billing_info?.billing_provider_name, 'billing_provider_name', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="billing_provider_name" data-section="billing_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Provider NPI</th>
                            <td>${createEditableField(jsonDetails.billing_info?.billing_provider_npi, 'billing_provider_npi', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="billing_provider_npi" data-section="billing_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Provider TIN</th>
                            <td>${createEditableField(jsonDetails.billing_info?.billing_provider_tin, 'billing_provider_tin', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="billing_provider_tin" data-section="billing_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Account Number</th>
                            <td>${createEditableField(jsonDetails.billing_info?.patient_account_no, 'patient_account_no', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="patient_account_no" data-section="billing_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Total Charge</th>
                            <td>${createEditableField(jsonDetails.billing_info?.total_charge, 'total_charge', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="total_charge" data-section="billing_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">Service Lines</h6>
                <button class="btn btn-primary btn-sm save-section" data-section="service_lines" style="display: none;">Save Changes</button>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>DOS</th>
                                <th>CPT</th>
                                <th>Modifier</th>
                                <th>Units</th>
                                <th>Diagnosis</th>
                                <th>Place of Service</th>
                                <th>Charge</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(jsonDetails.service_lines || []).map((line, index) => `
                                <tr>
                                    <td>${createEditableField(line.date_of_service, 'date_of_service', 'service_lines', index)}</td>
                                    <td>${createEditableField(line.cpt_code, 'cpt_code', 'service_lines', index)}</td>
                                    <td>${createEditableField(line.modifiers?.join(', '), 'modifiers', 'service_lines', index)}</td>
                                    <td>${createEditableField(line.units, 'units', 'service_lines', index)}</td>
                                    <td>${createEditableField(line.diagnosis_pointer, 'diagnosis_pointer', 'service_lines', index)}</td>
                                    <td>${createEditableField(line.place_of_service, 'place_of_service', 'service_lines', index)}</td>
                                    <td>${createEditableField(line.charge_amount, 'charge_amount', 'service_lines', index)}</td>
                                    <td>
                                        <button class="btn btn-sm btn-outline-primary edit-field" data-field="service_lines" data-section="service_lines" data-index="${index}">
                                            Edit
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header">
                <h6 class="mb-0">Validation Messages</h6>
            </div>
            <div class="card-body">
                <ul class="list-group">
                    ${(jsonDetails.validation_messages || []).map(msg => `
                        <li class="list-group-item">${msg}</li>
                    `).join('')}
                </ul>
            </div>
        </div>
    `;

    // Add event listeners for edit functionality
    const editButtons = hcfaDetails.querySelectorAll('.edit-field');
    const saveButtons = hcfaDetails.querySelectorAll('.save-section');
    let editedFields = new Set();

    editButtons.forEach(button => {
        button.addEventListener('click', () => {
            const field = button.dataset.field;
            const section = button.dataset.section;
            const index = button.dataset.index;
            
            // Find the editable field container
            const editableField = button.closest('td').querySelector('.editable-field');
            if (!editableField) return;
            
            const input = editableField.querySelector('.editable-input');
            const display = editableField.querySelector('.editable-display');
            
            if (button.textContent === 'Edit') {
                // Show input and hide display
                display.style.display = 'none';
                input.style.display = 'block';
                input.focus(); // Focus the input field
                
                button.textContent = 'Cancel';
                button.classList.remove('btn-outline-primary');
                button.classList.add('btn-outline-danger');
                editedFields.add(`${section}:${field}:${index || ''}`);
            } else {
                // Hide input and show display
                input.style.display = 'none';
                display.style.display = 'block';
                
                button.textContent = 'Edit';
                button.classList.remove('btn-outline-danger');
                button.classList.add('btn-outline-primary');
                editedFields.delete(`${section}:${field}:${index || ''}`);
            }
            
            // Show/hide save button for the section
            const sectionSaveButton = hcfaDetails.querySelector(`.save-section[data-section="${section}"]`);
            if (sectionSaveButton) {
                const hasSectionEdits = Array.from(editedFields).some(f => f.startsWith(section + ':'));
                sectionSaveButton.style.display = hasSectionEdits ? 'block' : 'none';
            }
        });
    });

    // Add input event listeners to update display values in real-time
    hcfaDetails.querySelectorAll('.editable-input').forEach(input => {
        input.addEventListener('input', () => {
            const field = input.dataset.field;
            const section = input.dataset.section;
            const index = input.dataset.index;
            const display = hcfaDetails.querySelector(`.editable-display[data-field="${field}"][data-section="${section}"]${index !== null ? `[data-index="${index}"]` : ''}`);
            if (display) {
                display.textContent = input.value || 'N/A';
            }
        });
    });

    // Add keyboard event listeners for better UX
    hcfaDetails.querySelectorAll('.editable-input').forEach(input => {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const section = input.dataset.section;
                const sectionSaveButton = hcfaDetails.querySelector(`.save-section[data-section="${section}"]`);
                if (sectionSaveButton) {
                    sectionSaveButton.click();
                }
            } else if (e.key === 'Escape') {
                const field = input.dataset.field;
                const section = input.dataset.section;
                const index = input.dataset.index;
                const button = hcfaDetails.querySelector(`.edit-field[data-field="${field}"][data-section="${section}"]${index !== null ? `[data-index="${index}"]` : ''}`);
                if (button) {
                    button.click(); // This will cancel the edit
                }
            }
        });
    });

    saveButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const section = button.dataset.section;
            showLoading();
            try {
                const updatedData = { ...window.currentDocumentData };
                
                // Get all edited fields for this section
                const sectionEdits = Array.from(editedFields)
                    .filter(f => f.startsWith(section + ':'))
                    .map(f => f.split(':'));
                
                sectionEdits.forEach(([_, field, index]) => {
                    const input = hcfaDetails.querySelector(`.editable-input[data-field="${field}"][data-section="${section}"]${index ? `[data-index="${index}"]` : ''}`);
                    if (!input) return;
                    
                    if (section === 'service_lines') {
                        // Handle service lines array
                        if (!updatedData.service_lines[index]) {
                            updatedData.service_lines[index] = {};
                        }
                        if (field === 'modifiers') {
                            // Convert comma-separated string back to array
                            updatedData.service_lines[index][field] = input.value.split(',').map(m => m.trim()).filter(m => m);
                        } else {
                            updatedData.service_lines[index][field] = input.value;
                        }
                    } else if (section === 'root') {
                        // Handle root-level fields
                        updatedData[field] = input.value;
                    } else {
                        // Handle nested fields
                        if (!updatedData[section]) {
                            updatedData[section] = {};
                        }
                        updatedData[section][field] = input.value;
                    }
                });

                const response = await fetch(`/api/failures/${currentDocument.filename}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(updatedData)
                });

                if (!response.ok) {
                    throw new Error('Failed to save changes');
                }

                // Reset UI for this section
                sectionEdits.forEach(([_, field, index]) => {
                    const input = hcfaDetails.querySelector(`.editable-input[data-field="${field}"][data-section="${section}"]${index ? `[data-index="${index}"]` : ''}`);
                    const display = hcfaDetails.querySelector(`.editable-display[data-field="${field}"][data-section="${section}"]${index ? `[data-index="${index}"]` : ''}`);
                    const editButton = hcfaDetails.querySelector(`.edit-field[data-field="${field}"][data-section="${section}"]${index ? `[data-index="${index}"]` : ''}`);
                    
                    if (display) display.textContent = input.value || 'N/A';
                    if (display) display.style.display = 'block';
                    if (input) input.style.display = 'none';
                    if (editButton) {
                        editButton.textContent = 'Edit';
                        editButton.classList.remove('btn-outline-danger');
                        editButton.classList.add('btn-outline-primary');
                    }
                });

                // Remove edited fields for this section
                editedFields = new Set(Array.from(editedFields).filter(f => !f.startsWith(section + ':')));
                
                // Hide save button if no more edits
                if (editedFields.size === 0) {
                    button.style.display = 'none';
                }
                
                showSuccess('Changes saved successfully');
                
                // Refresh the document list
                loadFailures();
                
            } catch (error) {
                console.error('Error saving changes:', error);
                showError('Failed to save changes');
            } finally {
                hideLoading();
            }
        });
    });

    // Display DB details if available
    const dbDetailsPanel = document.getElementById('dbDetails');
    if (dbDetails) {
        dbDetailsPanel.innerHTML = `
            <div class="card mb-4">
                <div class="card-header">
                    <h6 class="mb-0">Order Details</h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <tr>
                                <th>Order ID</th>
                                <td>${dbDetails.order_details?.Order_ID || 'N/A'}</td>
                            </tr>
                            <tr>
                                <th>Status</th>
                                <td>${dbDetails.order_details?.status || 'N/A'}</td>
                            </tr>
                            <tr>
                                <th>Bundle Type</th>
                                <td>${dbDetails.order_details?.bundle_type || 'N/A'}</td>
                            </tr>
                            <tr>
                                <th>Created Date</th>
                                <td>${dbDetails.order_details?.created_date || 'N/A'}</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-header">
                    <h6 class="mb-0">Provider Details</h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <tr>
                                <th>Name</th>
                                <td>${dbDetails.provider_details?.provider_name || 'N/A'}</td>
                            </tr>
                            <tr>
                                <th>NPI</th>
                                <td>${dbDetails.provider_details?.npi || 'N/A'}</td>
                            </tr>
                            <tr>
                                <th>Tax ID</th>
                                <td>${dbDetails.provider_details?.tin || 'N/A'}</td>
                            </tr>
                            <tr>
                                <th>Network Status</th>
                                <td>${dbDetails.provider_details?.network_status || 'N/A'}</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-header">
                    <h6 class="mb-0">Line Items</h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>DOS</th>
                                    <th>CPT</th>
                                    <th>Modifier</th>
                                    <th>Units</th>
                                    <th>Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(dbDetails.line_items || []).map(item => `
                                    <tr>
                                        <td>${item.DOS || 'N/A'}</td>
                                        <td>${item.CPT || 'N/A'}</td>
                                        <td>${item.Modifier || 'N/A'}</td>
                                        <td>${item.Units || 'N/A'}</td>
                                        <td>${item.Description || 'N/A'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    } else {
        dbDetailsPanel.innerHTML = `
            <div class="alert alert-warning">
                Database details not available for this order.
            </div>
        `;
    }
}

// Filter documents
function filterDocuments(searchText, status = 'all') {
    const filtered = allDocuments.filter(doc => {
        const matchesSearch = searchText === '' || 
            doc.filename.toLowerCase().includes(searchText.toLowerCase()) ||
            doc.order_id?.toLowerCase().includes(searchText.toLowerCase()) ||
            doc.patient_name?.toLowerCase().includes(searchText.toLowerCase());
        
        const matchesStatus = status === 'all' || doc.status === status;
        
        return matchesSearch && matchesStatus;
    });
    
    renderDocumentList(filtered);
}

// Loading state
function showLoading() {
    document.getElementById('loadingOverlay').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

// Error handling
function showError(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('.container-fluid').insertBefore(alert, document.querySelector('.row'));
    setTimeout(() => alert.remove(), 5000);
}

function showSuccess(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-success alert-dismissible fade show';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('.container-fluid').insertBefore(alert, document.querySelector('.row'));
    setTimeout(() => alert.remove(), 5000);
}