/**
 * OTA Correction Module for BRSystem
 * Handles OTA corrections for out-of-network providers with rate validation failures
 */

// Global variables to store current modal data
let currentOrderId = '';
let currentFailureData = null;
let otaLineItemRates = [];

// Define and export the showOTACorrectionModal function immediately
window.showOTACorrectionModal = function(failure) {
    console.log('OTA correction modal function called');
    console.log('Checking if document qualifies for OTA correction:', failure);
    
    // Check if this is a rate validation failure
    if (!isRateValidationFailure(failure)) {
        showErrorMessage('This document does not have any rate validation failures.');
        return;
    }
    
    // Get provider info from the correct location in the data structure
    const providerInfo = failure.database_details?.provider_details || {};
    console.log('Provider info from database details:', providerInfo);
    
    if (!isOutOfNetworkProvider(providerInfo)) {
        showErrorMessage('Rate correction is only available for out-of-network providers. This provider is in-network.');
        return;
    }
    
    console.log('Document qualifies for OTA correction');
    
    // Store current failure data
    currentFailureData = failure;
    currentOrderId = failure.Order_ID || '';
    
    if (!currentOrderId) {
        console.error('No Order ID found in failure data');
        showErrorMessage('No Order ID found in failure data');
        return;
    }
    
    // Set provider information in modal
    const providerNameElement = document.getElementById('provider-name-ota');
    const providerNetworkElement = document.getElementById('provider-network-ota');
    const orderIdElement = document.getElementById('order-id-ota');
    
    if (!providerNameElement || !providerNetworkElement || !orderIdElement) {
        console.error('Required modal elements not found');
        showErrorMessage('Error: Required modal elements not found. Please refresh the page and try again.');
        return;
    }
    
    providerNameElement.textContent = providerInfo.provider_name || 'Unknown Provider';
    providerNetworkElement.textContent = providerInfo.provider_network || 'Out of Network';
    orderIdElement.textContent = currentOrderId;
    
    // Populate line items table
    populateOTALineItemsTable(failure);
    
    // Show the modal
    const modalElement = document.getElementById('otaCorrectionModal');
    if (!modalElement) {
        console.error('OTA correction modal element not found');
        showErrorMessage('Error: OTA correction modal element not found. Please refresh the page and try again.');
        return;
    }
    
    // Check if Bootstrap is loaded
    if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    } else {
        // Fallback if Bootstrap is not loaded
        modalElement.style.display = 'block';
        modalElement.classList.add('show');
        document.body.classList.add('modal-open');
    }
};

/**
 * Check if a failure is a rate validation failure
 * @param {Object} failure - The failure data object
 * @returns {boolean} - True if the failure is a rate validation failure
 */
function isRateValidationFailure(failure) {
    if (!failure) {
        console.log('No failure data provided');
        return false;
    }
    
    // Log the entire failure object for debugging
    console.log('Checking failure object:', failure);
    
    // Check validation type first
    if (failure.validation_type === 'rate') {
        console.log('Rate validation failure detected by validation_type');
        return true;
    }
    
    // Check validation message
    if (failure.validation_message) {
        const message = failure.validation_message.toLowerCase();
        const rateTerms = ['rate', 'rates', 'pricing', 'price', 'cost', 'amount'];
        
        const isRateFailure = rateTerms.some(term => message.includes(term));
        console.log('Rate validation failure check by message:', {
            message,
            isRateFailure,
            checkedTerms: rateTerms
        });
        
        if (isRateFailure) {
            return true;
        }
    }
    
    // Check if there are rate-related fields
    if (failure.service_lines || failure.line_items) {
        console.log('Rate validation failure detected by presence of service lines or line items');
        return true;
    }
    
    console.log('Not a rate validation failure');
    return false;
}

/**
 * Check if a provider is out-of-network
 * @param {Object} providerInfo - The provider information
 * @returns {boolean} - True if the provider is out-of-network
 */
function isOutOfNetworkProvider(providerInfo) {
    if (!providerInfo) {
        console.log('Provider info missing');
        return false;
    }
    
    // Log the entire provider info for debugging
    console.log('Provider info structure:', providerInfo);
    
    // Check if the network status is directly in the data
    const networkStatus = providerInfo['In Network'] || 
                         providerInfo['In Network Provider'] ||
                         providerInfo.Provider_Network || 
                         providerInfo.provider_network || 
                         providerInfo.network_status ||
                         providerInfo.Network_Status;
    
    if (!networkStatus) {
        console.log('Network status missing from provider info:', providerInfo);
        return false;
    }
    
    const network = networkStatus.toLowerCase();
    const outNetworkTerms = ['out of network', 'out-of-network', 'outnetwork', 'out network provider'];
    
    const isOutNetwork = outNetworkTerms.some(term => network.includes(term));
    console.log('Network status check:', {
        networkStatus,
        isOutNetwork,
        checkedTerms: outNetworkTerms
    });
    
    return isOutNetwork;
}

/**
 * Populate the OTA line items table with rate failure data
 * @param {Object} failure - The failure data object
 */
function populateOTALineItemsTable(failure) {
    const tableBody = document.getElementById('ota-items-body');
    tableBody.innerHTML = '';
    otaLineItemRates = [];
    
    console.log('Populating OTA line items table with failure data:', failure);
    
    // Try to get rates from different possible locations
    let rates = [];
    
    // Check service lines first (this is where the rate data is)
    if (failure.service_lines && Array.isArray(failure.service_lines)) {
        console.log('Found service lines:', failure.service_lines);
        rates = failure.service_lines.map(item => ({
            cpt: item.cpt_code,
            description: item.description || item.proc_desc || '',
            rate: parseFloat(item.charge_amount) || 0,
            modifier: Array.isArray(item.modifiers) ? item.modifiers.join(', ') : (item.modifiers || '')
        }));
    }
    // Check line items as fallback
    else if (failure.line_items) {
        console.log('Found line items:', failure.line_items);
        rates = failure.line_items.map(item => ({
            cpt: item.cpt_code || item.proc_cd || item.cpt,
            description: item.description || item.proc_desc || '',
            rate: parseFloat(item.charge_amount || item.rate || item.amount || 0),
            modifier: item.modifier || ''
        }));
    }
    
    if (rates.length === 0) {
        console.log('No rates found in any location');
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="5" class="text-center">No line items found</td>';
        tableBody.appendChild(row);
        return;
    }
    
    console.log('Processing rates for display:', rates);
    
    // Check for existing OTAs
    fetchExistingOTAs(currentOrderId)
        .then(existingOTAs => {
            console.log('Existing OTAs:', existingOTAs);
            
            // Add each line item to the table
            rates.forEach((rate, index) => {
                const cptCode = rate.cpt || '';
                const description = rate.description || '';
                const currentRate = rate.rate || 0;
                const modifier = rate.modifier || '';
                
                // Check if there's an existing OTA for this CPT
                const existingOTA = existingOTAs.find(ota => 
                    ota.cpt_code === cptCode && ota.modifier === modifier);
                
                const otaRate = existingOTA ? existingOTA.rate : '';
                
                console.log('Processing rate item:', { cptCode, description, currentRate, modifier, otaRate });
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${cptCode}</td>
                    <td class="description-cell">${description}</td>
                    <td>${modifier}</td>
                    <td>$${currentRate.toFixed(2)}</td>
                    <td>
                        <input 
                            type="number" 
                            class="form-control ota-rate-input" 
                            data-index="${index}" 
                            data-cpt="${cptCode}"
                            data-modifier="${modifier}" 
                            min="0" 
                            step="0.01"
                            value="${otaRate}">
                    </td>
                `;
                tableBody.appendChild(row);
                
                // Store line item for later use
                otaLineItemRates.push({
                    cpt_code: cptCode,
                    modifier: modifier,
                    rate: otaRate !== '' ? parseFloat(otaRate) : null
                });
            });
            
            // Add event listeners to rate inputs
            const rateInputs = document.querySelectorAll('.ota-rate-input');
            rateInputs.forEach(input => {
                input.addEventListener('input', function() {
                    const index = parseInt(this.dataset.index);
                    const rate = parseFloat(this.value);
                    
                    if (!isNaN(rate) && rate >= 0) {
                        this.classList.remove('is-invalid');
                        otaLineItemRates[index].rate = rate;
                    } else {
                        this.classList.add('is-invalid');
                        otaLineItemRates[index].rate = null;
                    }
                });
            });
        })
        .catch(error => {
            console.error('Error fetching existing OTAs:', error);
            showErrorMessage('Error fetching existing OTAs: ' + error.message);
        });
}

/**
 * Fetch existing OTAs for an order
 * @param {string} orderId - The order ID
 * @returns {Promise<Array>} - Promise resolving to array of OTAs
 */
async function fetchExistingOTAs(orderId) {
    if (!orderId) {
        return [];
    }
    
    try {
        const response = await fetch(`/api/otas/order/${orderId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            return data.ota_rates || [];
        } else {
            console.error('Error fetching OTAs:', data.error);
            return [];
        }
    } catch (error) {
        console.error('Error fetching OTAs:', error);
        return [];
    }
}

/**
 * Save the OTA corrections
 */
async function saveOTACorrections() {
    try {
        // Filter out items with no rate
        const validRates = otaLineItemRates.filter(item => item.rate !== null);
        
        if (validRates.length === 0) {
            showErrorMessage('Please enter at least one valid rate');
            return;
        }
        
        const response = await fetch('/api/otas/correct/line-items', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                order_id: currentOrderId,
                line_items: validRates
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to save OTA corrections');
        }
        
        const result = await response.json();
        
        // Close the modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('otaCorrectionModal'));
        modal.hide();
        
        // Show success message
        showSuccessMessage('OTA corrections saved successfully');
        
        // Update the UI to reflect the resolved failure
        updateFailureStatus(currentFailureData);
        
    } catch (error) {
        console.error('Error saving OTA corrections:', error);
        showErrorMessage(error.message || 'Failed to save OTA corrections');
    }
}

/**
 * Show a success message
 * @param {string} message - The message to display
 */
function showSuccessMessage(message) {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = 'alert alert-success alert-dismissible fade show success-message';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to document
    document.body.appendChild(alert);
    
    // Remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
        }
    }, 5000);
}

/**
 * Show an error message
 * @param {string} message - The message to display
 */
function showErrorMessage(message) {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show success-message';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to document
    document.body.appendChild(alert);
    
    // Remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
        }
    }, 5000);
}

/**
 * Update the failure status in the UI after successful correction
 * @param {Object} failure - The failure data object
 */
function updateFailureStatus(failure) {
    // Find the failure item in the UI and update its status
    const failureId = failure.file_name || '';
    
    // Find the failure element
    const failureElement = document.querySelector(`.document-item[data-filename="${failureId}"]`);
    if (failureElement) {
        // Add a resolved badge
        const badge = document.createElement('span');
        badge.className = 'badge bg-success ms-2';
        badge.textContent = 'Resolved';
        
        const existingBadge = failureElement.querySelector('.badge.bg-success');
        if (!existingBadge) {
            failureElement.appendChild(badge);
        }
        
        // Update the status badge if present
        const statusBadge = failureElement.querySelector('.status-badge');
        if (statusBadge) {
            statusBadge.className = 'status-badge';
            statusBadge.textContent = 'Resolved';
        }
    }
    
    // If details are currently displayed for this failure, update them
    if (currentDocument && currentDocument.filename === failureId) {
        // Add a resolved message to the validation messages
        const messagesElement = document.querySelector('.validation-message');
        if (messagesElement) {
            messagesElement.innerHTML += '<br><span class="text-success fw-bold">✓ OTA rates added successfully</span>';
        }
        
        // Disable the fix button if it exists
        const otaButton = document.getElementById('add-ota-button');
        if (otaButton) {
            otaButton.disabled = true;
            otaButton.textContent = 'OTA Rates Added';
            otaButton.classList.remove('btn-primary');
            otaButton.classList.add('btn-success');
        }
    }
}

// Attach event listeners when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Attach save button click event
    const saveButton = document.getElementById('save-ota-corrections');
    if (saveButton) {
        saveButton.addEventListener('click', saveOTACorrections);
    }
}); 