// Patient Editor functionality
let patientData = null;

function initializePatientEditor(data) {
    patientData = data;
    updatePatientFields();
    setupPatientEventListeners();
}

function updatePatientFields() {
    if (!patientData) return;

    // Update patient info fields
    document.getElementById('patientName').value = patientData.patient_info?.patient_name || '';
    document.getElementById('patientDOB').value = patientData.patient_info?.patient_dob || '';
    document.getElementById('patientZip').value = patientData.patient_info?.patient_zip || '';
    
    // Update billing info fields
    document.getElementById('totalCharge').value = patientData.billing_info?.total_charge || '';
    document.getElementById('patientAccountNo').value = patientData.billing_info?.patient_account_no || '';
}

function setupPatientEventListeners() {
    // Patient info fields
    document.getElementById('patientName').addEventListener('change', (e) => {
        updatePatientField('patient_info.patient_name', e.target.value);
    });
    
    document.getElementById('patientDOB').addEventListener('change', (e) => {
        updatePatientField('patient_info.patient_dob', e.target.value);
    });
    
    document.getElementById('patientZip').addEventListener('change', (e) => {
        updatePatientField('patient_info.patient_zip', e.target.value);
    });
    
    // Billing info fields
    document.getElementById('totalCharge').addEventListener('change', (e) => {
        updatePatientField('billing_info.total_charge', e.target.value);
    });
    
    document.getElementById('patientAccountNo').addEventListener('change', (e) => {
        updatePatientField('billing_info.patient_account_no', e.target.value);
    });
}

function updatePatientField(fieldPath, value) {
    if (!patientData) return;
    
    const fields = fieldPath.split('.');
    let current = patientData;
    
    // Navigate to the correct nested object
    for (let i = 0; i < fields.length - 1; i++) {
        if (!current[fields[i]]) {
            current[fields[i]] = {};
        }
        current = current[fields[i]];
    }
    
    // Update the value
    current[fields[fields.length - 1]] = value;
    
    // Enable save button
    document.getElementById('saveButton').disabled = false;
}

// Export functions for use in main.js
window.initializePatientEditor = initializePatientEditor;
window.updatePatientFields = updatePatientFields; 