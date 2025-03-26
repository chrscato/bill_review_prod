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
        const response = await fetch(`/api/failures/${doc.filename}`);
        const data = await response.json();
        displayDetails(data);
    } catch (error) {
        console.error('Error loading document details:', error);
        showError('Failed to load document details');
    } finally {
        hideLoading();
    }
}

// Display document details
function displayDetails(data) {
    // Extract data from the response
    const details = data.data || data;
    
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
                            <td>${details.patient_info?.patient_name || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>DOB</th>
                            <td>${details.patient_info?.patient_dob || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Zip Code</th>
                            <td>${details.patient_info?.patient_zip || 'N/A'}</td>
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
                            <td>${details.Order_ID || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Provider Name</th>
                            <td>${details.billing_info?.billing_provider_name || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Provider NPI</th>
                            <td>${details.billing_info?.billing_provider_npi || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Provider TIN</th>
                            <td>${details.billing_info?.billing_provider_tin || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Account Number</th>
                            <td>${details.billing_info?.patient_account_no || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Total Charge</th>
                            <td>$${details.billing_info?.total_charge || '0.00'}</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h6 class="mb-0">Service Lines</h6>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Place</th>
                                <th>CPT</th>
                                <th>Mods</th>
                                <th>Dx</th>
                                <th>Units</th>
                                <th>Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${details.service_lines ? details.service_lines.map(line => `
                                <tr>
                                    <td>${line.date_of_service || 'N/A'}</td>
                                    <td>${line.place_of_service || 'N/A'}</td>
                                    <td>${line.cpt_code || 'N/A'}</td>
                                    <td>${line.modifiers?.join(', ') || 'N/A'}</td>
                                    <td>${line.diagnosis_pointer || 'N/A'}</td>
                                    <td>${line.units || 'N/A'}</td>
                                    <td>$${line.charge_amount || '0.00'}</td>
                                </tr>
                            `).join('') : '<tr><td colspan="7">No service lines available</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    // Display DB details
    const dbDetails = document.getElementById('dbDetails');
    dbDetails.innerHTML = `
        <div class="card mb-4">
            <div class="card-header">
                <h6 class="mb-0">Order Details</h6>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <tr>
                            <th>Order ID</th>
                            <td>${details.Order_ID || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>Filemaker Number</th>
                            <td>${details.filemaker_number || 'N/A'}</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h6 class="mb-0">Validation Messages</h6>
            </div>
            <div class="card-body">
                <div class="validation-messages">
                    ${details.validation_messages ? details.validation_messages.map(msg => `
                        <div class="alert alert-info mb-2">
                            <pre class="mb-0">${msg}</pre>
                        </div>
                    `).join('') : '<div class="alert alert-info">No validation messages available</div>'}
                </div>
            </div>
        </div>
    `;

    // Display validation messages in the right panel
    const messagesContainer = document.getElementById('messageList');
    messagesContainer.innerHTML = '';
    if (details.validation_messages) {
        details.validation_messages.forEach(msg => {
            const div = document.createElement('div');
            div.className = 'alert alert-info';
            div.innerHTML = `<pre class="validation-message">${msg}</pre>`;
            messagesContainer.appendChild(div);
        });
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