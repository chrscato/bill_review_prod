/**
 * OTA Correction Module for BRSystem
 * Handles OTA corrections for out-of-network providers with rate validation failures
 */

// Create a module to avoid global variable conflicts
const OTACorrectionModule = (function() {
    // Private variables
    let currentOrderId = '';
    let currentFailureData = null;
    let otaLineItemRates = [];

    // Function to close all modals
    function closeAllModals() {
        const rateCorrectionModal = document.getElementById('rateCorrectionModal');
        const otaCorrectionModal = document.getElementById('otaCorrectionModal');
        
        if (rateCorrectionModal) {
            const modal = bootstrap.Modal.getInstance(rateCorrectionModal);
            if (modal) modal.hide();
        }
        
        if (otaCorrectionModal) {
            const modal = bootstrap.Modal.getInstance(otaCorrectionModal);
            if (modal) modal.hide();
        }
    }

    // Define and export the showOTACorrectionModal function
    window.showOTACorrectionModal = function(failure) {
        try {
            console.log('Opening OTA Correction Modal');
            console.log('Checking if document qualifies for OTA correction:', failure);
            
            // Close any open modals first
            closeAllModals();
            
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
        } catch (error) {
            console.error('Error in showOTACorrectionModal:', error);
            showErrorMessage('Error opening OTA correction modal: ' + error.message);
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
        
        // Store the rates for later use
        otaLineItemRates = rates;
        
        // Populate the table
        rates.forEach((item, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.cpt}</td>
                <td>${item.description}</td>
                <td>${item.modifier}</td>
                <td>
                    <div class="input-group">
                        <span class="input-group-text">$</span>
                        <input type="number" 
                               class="form-control ota-rate-input" 
                               value="${item.rate.toFixed(2)}"
                               data-index="${index}"
                               step="0.01"
                               min="0">
                    </div>
                </td>
            `;
            tableBody.appendChild(row);
        });
    }

    // Return the public API
    return {
        showOTACorrectionModal: window.showOTACorrectionModal
    };
})(); 