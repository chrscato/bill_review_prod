/**
 * Editor functionality for OCR Corrections
 */

/**
 * Initialize the editor with default values
 */
function initializeEditor() {
    // Set default values for form fields
    document.getElementById('patientName').value = '';
    document.getElementById('patientDOB').value = '';
    document.getElementById('patientZip').value = '';
    
    // Clear service lines
    document.getElementById('serviceLines').innerHTML = '';
    
    // Disable buttons
    document.getElementById('saveButton').disabled = true;
    document.getElementById('prevButton').disabled = true;
    document.getElementById('nextButton').disabled = true;
}

/**
 * Add a new service line
 */
function addServiceLine() {
    if (!currentData) {
        currentData = {};
    }
    
    if (!currentData.service_lines) {
        currentData.service_lines = [];
    }
    
    // Add a new empty service line
    currentData.service_lines.push({
        date_of_service: '',
        cpt_code: '',
        units: 1,
        charge_amount: ''
    });
    
    // Refresh the display
    displayData();
}

/**
 * Remove a service line
 * @param {number} index - Index of the service line to remove
 */
function removeServiceLine(index) {
    if (currentData && currentData.service_lines) {
        currentData.service_lines.splice(index, 1);
        displayData();
    }
}

/**
 * Validate the current data
 * @returns {boolean} - True if data is valid, false otherwise
 */
function validateData() {
    if (!currentData) {
        return false;
    }
    
    // Validate patient info
    if (!currentData.patient_info) {
        alert('Patient information is required');
        return false;
    }
    
    if (!currentData.patient_info.patient_name) {
        alert('Patient name is required');
        return false;
    }
    
    if (!currentData.patient_info.patient_dob) {
        alert('Patient date of birth is required');
        return false;
    }
    
    // Validate service lines
    if (!currentData.service_lines || currentData.service_lines.length === 0) {
        alert('At least one service line is required');
        return false;
    }
    
    for (let i = 0; i < currentData.service_lines.length; i++) {
        const line = currentData.service_lines[i];
        
        if (!line.date_of_service) {
            alert(`Date of service is required for service line ${i + 1}`);
            return false;
        }
        
        if (!line.cpt_code) {
            alert(`CPT code is required for service line ${i + 1}`);
            return false;
        }
        
        if (!line.units || line.units < 1) {
            alert(`Valid units are required for service line ${i + 1}`);
            return false;
        }
        
        if (!line.charge_amount) {
            alert(`Charge amount is required for service line ${i + 1}`);
            return false;
        }
    }
    
    return true;
}

/**
 * Format a date string
 * @param {string} dateStr - Date string to format
 * @returns {string} - Formatted date string
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    } catch (error) {
        console.error('Error formatting date:', error);
        return dateStr;
    }
}

/**
 * Format a currency amount
 * @param {string} amount - Amount to format
 * @returns {string} - Formatted currency string
 */
function formatCurrency(amount) {
    if (!amount) return '';
    
    try {
        const num = parseFloat(amount);
        return num.toLocaleString('en-US', {
            style: 'currency',
            currency: 'USD'
        });
    } catch (error) {
        console.error('Error formatting currency:', error);
        return amount;
    }
}

/**
 * Compare two data objects for changes
 * @param {object} original - Original data
 * @param {object} current - Current data
 * @returns {object} - Object containing changed fields
 */
function compareData(original, current) {
    const changes = {};
    
    // Compare patient info
    if (original.patient_info && current.patient_info) {
        for (const key in current.patient_info) {
            if (original.patient_info[key] !== current.patient_info[key]) {
                if (!changes.patient_info) {
                    changes.patient_info = {};
                }
                changes.patient_info[key] = {
                    original: original.patient_info[key],
                    current: current.patient_info[key]
                };
            }
        }
    }
    
    // Compare service lines
    if (original.service_lines && current.service_lines) {
        const lineChanges = [];
        
        for (let i = 0; i < current.service_lines.length; i++) {
            const currentLine = current.service_lines[i];
            const originalLine = original.service_lines[i] || {};
            const lineChange = {};
            
            for (const key in currentLine) {
                if (originalLine[key] !== currentLine[key]) {
                    lineChange[key] = {
                        original: originalLine[key],
                        current: currentLine[key]
                    };
                }
            }
            
            if (Object.keys(lineChange).length > 0) {
                lineChanges.push({
                    index: i,
                    changes: lineChange
                });
            }
        }
        
        if (lineChanges.length > 0) {
            changes.service_lines = lineChanges;
        }
    }
    
    return changes;
}

/**
 * Show a confirmation dialog
 * @param {string} message - Message to display
 * @returns {Promise<boolean>} - Promise that resolves to true if confirmed, false otherwise
 */
function showConfirmation(message) {
    return new Promise((resolve) => {
        if (confirm(message)) {
            resolve(true);
        } else {
            resolve(false);
        }
    });
}

/**
 * Show an error message
 * @param {string} message - Error message to display
 */
function showError(message) {
    alert(`Error: ${message}`);
}

/**
 * Show a success message
 * @param {string} message - Success message to display
 */
function showSuccess(message) {
    alert(message);
}

// Initialize the editor when the page loads
document.addEventListener('DOMContentLoaded', initializeEditor); 