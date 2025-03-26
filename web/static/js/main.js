// Global variables
let currentDocument = null;
let allDocuments = [];
let editedFields = new Set();

// Define the click handler function globally
function handleEditClick(event) {
    event.preventDefault(); // Prevent any default button behavior
    event.stopPropagation(); // Prevent event bubbling
    
    const button = event.currentTarget;
    const field = button.dataset.field;
    const section = button.dataset.section;
    const index = button.dataset.index;
    
    console.log('Edit button clicked:', { field, section, index }); // Debug log
    
    // Find the editable field container - look in the same td as the button
    const td = button.closest('td');
    if (!td) {
        console.error('Table cell not found'); // Debug log
        return;
    }
    
    // Find the editable field container within the same td
    const editableField = td.querySelector('.editable-field');
    if (!editableField) {
        console.error('Editable field container not found'); // Debug log
        return;
    }
    
    const input = editableField.querySelector('.editable-input');
    const display = editableField.querySelector('.editable-display');
    
    if (!input || !display) {
        console.error('Input or display element not found'); // Debug log
        return;
    }
    
    if (button.textContent === 'Edit') {
        // Show input and hide display
        editableField.classList.add('editing');
        input.focus(); // Focus the input field
        
        button.textContent = 'Cancel';
        button.classList.remove('btn-outline-primary');
        button.classList.add('btn-outline-danger');
        editedFields.add(`${section}:${field}:${index || ''}`);
    } else {
        // Hide input and show display
        editableField.classList.remove('editing');
        
        button.textContent = 'Edit';
        button.classList.remove('btn-outline-danger');
        button.classList.add('btn-outline-primary');
        editedFields.delete(`${section}:${field}:${index || ''}`);
    }
    
    // Show/hide save button for the section
    const sectionSaveButton = document.querySelector(`.save-section[data-section="${section}"]`);
    if (sectionSaveButton) {
        const hasSectionEdits = Array.from(editedFields).some(f => f.startsWith(section + ':'));
        sectionSaveButton.style.display = hasSectionEdits ? 'block' : 'none';
    }
}

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
                <span class="editable-display" data-field="${field}" data-section="${section}" ${dataAttr}>${displayValue}</span>
                <input type="text" 
                       class="form-control form-control-sm editable-input" 
                       value="${inputValue}"
                       data-field="${field}"
                       data-section="${section}"
                       ${dataAttr}>
            </div>
        `;
    };

    // Create service lines HTML
    const serviceLinesHtml = (jsonDetails.service_lines || []).map((line, index) => `
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
    `).join('');

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
                            <td>${createEditableField(jsonDetails.patient_info?.name, 'name', 'patient_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="name" data-section="patient_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>DOB</th>
                            <td>${createEditableField(formatDOB(jsonDetails.patient_info?.dob), 'dob', 'patient_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="dob" data-section="patient_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>ZIP</th>
                            <td>${createEditableField(jsonDetails.patient_info?.zip, 'zip', 'patient_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="zip" data-section="patient_info">
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
                            <th>Provider Name</th>
                            <td>${createEditableField(jsonDetails.billing_info?.provider_name, 'provider_name', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="provider_name" data-section="billing_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Provider NPI</th>
                            <td>${createEditableField(jsonDetails.billing_info?.provider_npi, 'provider_npi', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="provider_npi" data-section="billing_info">
                                    Edit
                                </button>
                            </td>
                        </tr>
                        <tr>
                            <th>Provider TIN</th>
                            <td>${createEditableField(jsonDetails.billing_info?.provider_tin, 'provider_tin', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="provider_tin" data-section="billing_info">
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
                        <tr>
                            <th>Account Number</th>
                            <td>${createEditableField(jsonDetails.billing_info?.account_number, 'account_number', 'billing_info')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary edit-field" data-field="account_number" data-section="billing_info">
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
                                <th>Date of Service</th>
                                <th>CPT</th>
                                <th>Modifier</th>
                                <th>Units</th>
                                <th>Description</th>
                                <th>Place of Service</th>
                                <th>Charge Amount</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${serviceLinesHtml}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    // Attach event listeners to all edit buttons
    const editButtons = hcfaDetails.querySelectorAll('.edit-field');
    editButtons.forEach(button => {
        // Remove any existing event listeners
        button.removeEventListener('click', handleEditClick);
        // Add the event listener
        button.addEventListener('click', handleEditClick);
    });

    // Attach event listeners to all save buttons
    const saveButtons = hcfaDetails.querySelectorAll('.save-section');
    saveButtons.forEach(button => {
        button.addEventListener('click', () => handleSaveClick(button.dataset.section));
    });

    // Attach event listeners to all input fields
    const inputFields = hcfaDetails.querySelectorAll('.editable-input');
    inputFields.forEach(input => {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const section = input.dataset.section;
                const saveButton = hcfaDetails.querySelector(`.save-section[data-section="${section}"]`);
                if (saveButton) {
                    handleSaveClick(section);
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                const button = input.closest('td').querySelector('.edit-field');
                if (button) {
                    handleEditClick({ currentTarget: button });
                }
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