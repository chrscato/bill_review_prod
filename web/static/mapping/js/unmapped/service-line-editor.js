// Service Line Editor functionality
let serviceLines = [];

function initializeServiceLineEditor(data) {
    serviceLines = data.service_lines || [];
    updateServiceLinesDisplay();
    setupServiceLineEventListeners();
}

function updateServiceLinesDisplay() {
    const container = document.getElementById('serviceLines');
    container.innerHTML = '';
    
    if (serviceLines.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No service lines found</div>';
        return;
    }
    
    serviceLines.forEach((line, index) => {
        const lineItem = document.createElement('div');
        lineItem.className = 'card mb-3 service-line-card';
        lineItem.innerHTML = `
            <div class="card-header d-flex justify-content-between align-items-center py-2">
                <h6 class="mb-0">Line Item ${index + 1}</h6>
                <button class="btn btn-sm btn-danger remove-line-item" data-index="${index}">
                    Remove
                </button>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-4">
                        <label class="form-label">Date of Service</label>
                        <input type="text" class="form-control mb-3" 
                               value="${line.date_of_service || ''}"
                               data-field="date_of_service">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Place of Service</label>
                        <input type="text" class="form-control mb-3"
                               value="${line.place_of_service || ''}"
                               data-field="place_of_service">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">CPT Code</label>
                        <input type="text" class="form-control mb-3"
                               value="${line.cpt_code || ''}"
                               data-field="cpt_code">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Modifiers</label>
                        <input type="text" class="form-control mb-3"
                               value="${line.modifiers ? line.modifiers.join(', ') : ''}"
                               data-field="modifiers">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Diagnosis Pointer</label>
                        <input type="text" class="form-control mb-3"
                               value="${line.diagnosis_pointer || ''}"
                               data-field="diagnosis_pointer">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Charge Amount</label>
                        <input type="text" class="form-control mb-3"
                               value="${line.charge_amount || ''}"
                               data-field="charge_amount">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Units</label>
                        <input type="text" class="form-control mb-3"
                               value="${line.units || ''}"
                               data-field="units">
                    </div>
                </div>
            </div>
        `;
        container.appendChild(lineItem);
    });
}

function setupServiceLineEventListeners() {
    // Add line item button
    document.getElementById('addLineItem').addEventListener('click', addLineItem);
    
    // Remove line item buttons
    document.querySelectorAll('.remove-line-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const index = parseInt(e.target.dataset.index);
            removeLineItem(index);
        });
    });
    
    // Line item field changes
    document.querySelectorAll('.service-line-card input').forEach(input => {
        input.addEventListener('change', (e) => {
            const index = parseInt(e.target.closest('.service-line-card').querySelector('.remove-line-item').dataset.index);
            const field = e.target.dataset.field;
            const value = field === 'modifiers' ? 
                e.target.value.split(',').map(m => m.trim()).filter(Boolean) : 
                e.target.value;
            
            updateLineItem(index, field, value);
        });
    });
}

function addLineItem() {
    serviceLines.push({
        date_of_service: '',
        place_of_service: '',
        cpt_code: '',
        modifiers: [],
        diagnosis_pointer: '',
        charge_amount: '',
        units: ''
    });
    
    updateServiceLinesDisplay();
    setupServiceLineEventListeners();
    document.getElementById('saveButton').disabled = false;
}

function removeLineItem(index) {
    serviceLines.splice(index, 1);
    updateServiceLinesDisplay();
    setupServiceLineEventListeners();
    document.getElementById('saveButton').disabled = false;
}

function updateLineItem(index, field, value) {
    if (index >= 0 && index < serviceLines.length) {
        serviceLines[index][field] = value;
        document.getElementById('saveButton').disabled = false;
    }
}

// Export functions for use in main.js
window.initializeServiceLineEditor = initializeServiceLineEditor;
window.getServiceLines = () => serviceLines; 