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
    document.getElementById('searchInput').addEventListener('input', function(e) {
        filterDocuments(e.target.value);
    });

    // Status filter
    document.getElementById('statusFilter').addEventListener('change', function(e) {
        filterDocuments(document.getElementById('searchInput').value, e.target.value);
    });

    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', loadFailures);

    // Message input
    document.getElementById('messageInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send message button
    document.getElementById('sendMessageBtn').addEventListener('click', sendMessage);
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
    
    // Display HCFA details
    const hcfaDetails = document.getElementById('hcfaDetails');
    hcfaDetails.innerHTML = `
        <div class="card mb-4">
            <div class="card-header">
                <h6 class="mb-0">Patient Information</h6>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <tr>
                            <th>Name</th>
                            <td>${jsonDetails.patient_info?.name || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>DOB</th>
                            <td>${jsonDetails.patient_info?.dob || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Zip Code</th>
                            <td>${jsonDetails.patient_info?.zip || 'N/A'}</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header">
                <h6 class="mb-0">Billing Information</h6>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <tr>
                            <th>Order ID</th>
                            <td>${jsonDetails.order_info?.order_id || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Provider Name</th>
                            <td>${jsonDetails.billing_info?.provider_name || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Provider NPI</th>
                            <td>${jsonDetails.billing_info?.provider_npi || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Total Charge</th>
                            <td>$${jsonDetails.billing_info?.total_charge || '0.00'}</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header">
                <h6 class="mb-0">Service Lines</h6>
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
                                <th>Charge</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(jsonDetails.service_lines || []).map(line => `
                                <tr>
                                    <td>${line.date_of_service || 'N/A'}</td>
                                    <td>${line.cpt || 'N/A'}</td>
                                    <td>${line.modifier || 'N/A'}</td>
                                    <td>${line.units || 'N/A'}</td>
                                    <td>${line.description || 'N/A'}</td>
                                    <td>$${line.charge_amount || '0.00'}</td>
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

// Send message
function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (message && currentDocument) {
        const messagesContainer = document.getElementById('messageList');
        const div = document.createElement('div');
        div.className = 'alert alert-info';
        div.innerHTML = `<pre class="validation-message">${message}</pre>`;
        messagesContainer.appendChild(div);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        input.value = '';
    }
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