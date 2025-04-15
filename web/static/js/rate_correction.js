/**
 * Rate Correction Module for BRSystem
 * Handles rate corrections for in-network providers with rate validation failures
 */

// Global variables to store current modal data
let currentProviderTin = '';
let currentFailureData = null;
let lineItemRates = [];
let categoryRates = {};
let ancillary_codes = { ancillary_codes: {} }; // Initialize with empty ancillary codes
let ancillaryCodesLoaded = false;

// Function to check if a code is ancillary
function isAncillaryCode(cptCode) {
    if (!ancillaryCodesLoaded) {
        console.warn('Ancillary codes not loaded yet, checking against empty list');
        return false;
    }
    return ancillary_codes.ancillary_codes[cptCode] === 'ancillary';
}

// Load ancillary codes configuration
async function loadAncillaryCodes() {
    try {
        const response = await fetch('/config/ancillary_codes.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data && data.ancillary_codes) {
            ancillary_codes = data;
            ancillaryCodesLoaded = true;
            console.log('Ancillary codes loaded:', ancillary_codes);
        } else {
            throw new Error('Invalid ancillary codes format');
        }
    } catch (error) {
        console.error('Error loading ancillary codes:', error);
        // Initialize with default ancillary codes if loading fails
        ancillary_codes = {
            ancillary_codes: {
                "Q9967": "ancillary",
                "Q9966": "ancillary",
                "A4550": "ancillary",
                "A9578": "ancillary",
                "A9575": "ancillary",
                "A9573": "ancillary",
                "A9585": "ancillary",
                "G9637": "ancillary",
                "G9322": "ancillary",
                "A9503": "ancillary"
            }
        };
        ancillaryCodesLoaded = true;
        console.log('Using default ancillary codes');
    }
}

// Load ancillary codes when the script loads
loadAncillaryCodes();

let availableCategories = {
  "MRI w/o": [
    "70551", "72141", "73721", "73718", "70540", "72195", 
    "72146", "73221", "73218"
  ],
  "MRI w/": [
    "70552", "72142", "73722", "70542", "72196", 
    "72147", "73222", "73219"
  ],
  "MRI w/&w/o": [
    "70553", "72156", "73723", "70543", "72197", 
    "72157", "73223", "73220"
  ],
  "CT w/o": [
    "74176", "74150", "72125", "70450", "73700", 
    "72131", "70486", "70480", "72192", "70490", 
    "72128", "71250", "73200"
  ],
  "CT w/": [
    "74177", "74160", "72126", "70460", "73701", 
    "72132", "70487", "70481", "72193", "70491", 
    "72129", "71260", "73201"
  ],
  "CT w/&w/o": [
    "74178", "74170", "72127", "70470", "73702", 
    "72133", "70488", "70482", "72194", "70492", 
    "72130", "71270", "73202"
  ],
  "Xray": [
    "74010", "74000", "74020", "76080", "73050", 
    "73600", "73610", "77072", "77073", "73650", 
    "72040", "72050", "71010", "71021", "71023", 
    "71022", "71020", "71030", "71034", "71035", "73130"
  ],
  "Ultrasound": [
    "76700", "76705", "76770", "76775", "76536",
    "76604", "76642", "76856", "76857", "76870", "76882"
  ]
};

// Helper function to check if a provider is in-network
function isInNetworkProvider(providerInfo) {
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
    const inNetworkTerms = ['in network', 'in-network', 'innetwork', 'in network provider'];
    
    const isInNetwork = inNetworkTerms.some(term => network.includes(term));
    console.log('Network status check:', {
        networkStatus,
        isInNetwork,
        checkedTerms: inNetworkTerms
    });
    
    return isInNetwork;
}

// Helper function to check if a failure is a rate validation failure
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
    
    // Check validation messages
    if (failure.validation_messages) {
        console.log('Validation messages:', failure.validation_messages);
        const hasRateFailure = failure.validation_messages.some(msg => 
            msg.toLowerCase().includes('rate validation failed') ||
            msg.toLowerCase().includes('rate issue') ||
            msg.toLowerCase().includes('rate problem') ||
            msg.toLowerCase().includes('rate correction needed'));
        console.log('Rate validation failure check by messages:', hasRateFailure);
        return hasRateFailure;
    }
    
    // Check for rate-related fields in the failure data
    if (failure.rates && failure.rates.length > 0) {
        console.log('Found rates in failure data:', failure.rates);
        return true;
    }
    
    // Check for rate validation in the database details
    if (failure.database_details?.validation_results?.rate_validation) {
        console.log('Found rate validation in database details');
        return true;
    }
    
    console.log('No rate validation failure detected');
    return false;
}

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

// Helper function to check if a CPT code is in any category
function isCPTInCategory(cptCode) {
    for (const [category, codes] of Object.entries(availableCategories)) {
        if (codes.includes(cptCode)) {
            return true;
        }
    }
    return false;
}

// Define and export the showRateCorrectionModal function immediately
window.showRateCorrectionModal = async function(failure, dbData) {
    try {
        console.log('Opening Rate Correction Modal');
        console.log('Checking if document qualifies for rate correction:', failure);
        
        // Close any open modals first
        closeAllModals();
        
        // Check if this is a rate validation failure
        if (!isRateValidationFailure(failure)) {
            showErrorMessage('This document does not have any rate validation failures.');
            return;
        }
        
        // Get provider info from either dbData or failure.database_details
        const providerInfo = dbData?.provider_details || failure.database_details?.provider_details || {};
        console.log('Provider info from database details:', providerInfo);
        
        if (!isInNetworkProvider(providerInfo)) {
            showErrorMessage('Rate correction is only available for in-network providers. This provider is out-of-network.');
            return;
        }
        
        console.log('Document qualifies for rate correction');
        
        // Store current failure data
        currentFailureData = failure;
        currentProviderTin = providerInfo.tin || '';
        
        // Clean TIN (remove non-digits)
        currentProviderTin = currentProviderTin.replace(/\D/g, '');
        
        // Set provider information in modal
        document.getElementById('provider-tin').textContent = currentProviderTin;
        document.getElementById('provider-name').textContent = providerInfo.provider_name || 'Unknown Provider';
        document.getElementById('provider-network').textContent = providerInfo.provider_network || providerInfo.network_status || 'Unknown';
        
        // Wait for ancillary codes to load if they haven't already
        if (!ancillaryCodesLoaded) {
            console.log('Waiting for ancillary codes to load...');
            await loadAncillaryCodes();
        }
        
        // Check for non-category CPT codes
        let nonCategoryCPTs = [];
        if (failure.line_items && Array.isArray(failure.line_items)) {
            nonCategoryCPTs = failure.line_items
                .filter(item => {
                    if (!item.cpt_code) return false;
                    // Check if the code is in the ancillary codes list
                    if (isAncillaryCode(item.cpt_code)) {
                        console.log(`Excluding ancillary code: ${item.cpt_code}`);
                        return false;
                    }
                    return !isCPTInCategory(item.cpt_code);
                })
                .map(item => item.cpt_code);
        } else if (failure.service_lines && Array.isArray(failure.service_lines)) {
            nonCategoryCPTs = failure.service_lines
                .filter(item => {
                    if (!item.cpt_code) return false;
                    // Check if the code is in the ancillary codes list
                    if (isAncillaryCode(item.cpt_code)) {
                        console.log(`Excluding ancillary code: ${item.cpt_code}`);
                        return false;
                    }
                    return !isCPTInCategory(item.cpt_code);
                })
                .map(item => item.cpt_code);
        }

        // If there are non-category CPT codes, show a warning message
        if (nonCategoryCPTs.length > 0) {
            const warningMessage = document.createElement('div');
            warningMessage.className = 'alert alert-warning mt-3';
            warningMessage.innerHTML = `
                <strong>Note:</strong> The following CPT codes are not in any predefined category:
                <ul class="mb-0 mt-2">
                    ${nonCategoryCPTs.map(cpt => `<li>${cpt}</li>`).join('')}
                </ul>
                <p class="mb-0 mt-2">These codes will need to be corrected individually in the Line Item Correction tab.</p>
            `;
            document.querySelector('.modal-body').insertBefore(warningMessage, document.querySelector('.nav-tabs'));
        }
        
        // Populate line items table
        populateLineItemsTable(failure);
        
        // Populate category table
        populateCategoryTable();
        
        // Show the modal
        const modalElement = document.getElementById('rateCorrectionModal');
        if (!modalElement) {
            console.error('Rate correction modal element not found');
            showErrorMessage('Error: Rate correction modal element not found. Please refresh the page and try again.');
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
        console.error('Error in showRateCorrectionModal:', error);
        showErrorMessage('Error opening rate correction modal: ' + error.message);
    }
};

/**
 * Populate the line items table with rate failure data
 * @param {Object} failure - The failure data object
 */
function populateLineItemsTable(failure) {
    const tableBody = document.getElementById('line-items-body');
    tableBody.innerHTML = '';
    lineItemRates = [];
    
    console.log('Populating line items table with failure data:', failure);
    
    // Try to get rates from different possible locations
    let rates = [];
    
    // Check line items in the main data structure
    if (failure.line_items && Array.isArray(failure.line_items)) {
        console.log('Found line items:', failure.line_items);
        rates = failure.line_items.map(item => ({
            cpt: item.cpt_code,
            description: item.description || item.proc_desc || '',
            rate: parseFloat(item.charge_amount) || 0,
            modifier: Array.isArray(item.modifiers) ? item.modifiers.join(', ') : (item.modifiers || '')
        }));
    }
    // Fallback to service lines if line_items not found
    else if (failure.service_lines && Array.isArray(failure.service_lines)) {
        console.log('Found service lines:', failure.service_lines);
        rates = failure.service_lines.map(item => ({
            cpt: item.cpt_code,
            description: item.description || item.proc_desc || '',
            rate: parseFloat(item.charge_amount) || 0,
            modifier: Array.isArray(item.modifiers) ? item.modifiers.join(', ') : (item.modifiers || '')
        }));
    }
    
    // Store the rates for later use
    lineItemRates = rates;
    
    // Populate the table
    rates.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.cpt}</td>
            <td>${item.description}</td>
            <td>
                <div class="input-group">
                    <span class="input-group-text">$</span>
                    <input type="number" 
                           class="form-control rate-input" 
                           value="${item.rate.toFixed(2)}"
                           data-index="${index}"
                           step="0.01"
                           min="0">
                </div>
            </td>
            <td>
                <input type="text" 
                       class="form-control modifier-input" 
                       value="${item.modifier}"
                       data-index="${index}"
                       placeholder="Enter modifier">
            </td>
        `;
        tableBody.appendChild(row);
    });
}

/**
 * Populate the category table with CPT code categories
 */
function populateCategoryTable() {
    const tableBody = document.getElementById('category-body');
    tableBody.innerHTML = '';
    categoryRates = {};
    
    // Add each category to the table
    Object.entries(availableCategories).forEach(([category, codes]) => {
        // Initialize the category in categoryRates
        categoryRates[category] = { rate: null, modifier: '' };
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${category}</td>
            <td>${codes.join(', ')}</td>
            <td>
                <div class="input-group">
                    <span class="input-group-text">$</span>
                    <input type="number" 
                           class="form-control rate-input" 
                           data-category="${category}"
                           step="0.01"
                           min="0">
                </div>
            </td>
            <td>
                <input type="text" 
                       class="form-control modifier-input" 
                       data-category="${category}"
                       placeholder="Enter modifier">
            </td>
        `;
        tableBody.appendChild(row);
    });

    // Add event listeners to rate inputs
    const rateInputs = tableBody.querySelectorAll('.rate-input');
    rateInputs.forEach(input => {
        input.addEventListener('input', function() {
            const category = this.dataset.category;
            const rate = this.value.trim() === '' ? null : parseFloat(this.value);
            
            console.log('Rate input changed:', {
                category,
                value: this.value,
                parsedRate: rate
            });
            
            if (rate === null || (!isNaN(rate) && rate >= 0)) {
                this.classList.remove('is-invalid');
                if (category !== undefined) {
                    // Category rate
                    if (!categoryRates[category]) {
                        categoryRates[category] = { rate: null, modifier: '' };
                    }
                    categoryRates[category].rate = rate;
                    console.log('Updated categoryRates:', categoryRates);
                }
            } else {
                this.classList.add('is-invalid');
                if (category !== undefined) {
                    if (categoryRates[category]) {
                        categoryRates[category].rate = null;
                    }
                }
            }
        });
    });

    // Add event listeners to modifier inputs
    const modifierInputs = tableBody.querySelectorAll('.modifier-input');
    modifierInputs.forEach(input => {
        input.addEventListener('input', function() {
            const category = this.dataset.category;
            const modifier = this.value.trim();
            
            if (category !== undefined) {
                // Category modifier
                if (!categoryRates[category]) {
                    categoryRates[category] = { rate: null, modifier: '' };
                }
                categoryRates[category].modifier = modifier;
            }
        });
    });
}

/**
 * Save the rate corrections
 */
async function saveRateCorrections() {
  // Determine which tab is active
  const lineItemTab = document.getElementById('line-item-correction');
  const isLineItemActive = lineItemTab.classList.contains('show');
  
  try {
    // Validate currentProviderTin
    if (!currentProviderTin) {
      showErrorMessage('Provider TIN is missing. Please try reopening the rate correction modal.');
      return;
    }

    let response;
    
    if (isLineItemActive) {
      // Save line item corrections
      const validRates = lineItemRates.filter(item => item.rate !== null);
      
      if (validRates.length === 0) {
        showErrorMessage('Please enter at least one valid rate');
        return;
      }
      
      // Add modifiers to the line items (can be empty string)
      const lineItemsWithModifiers = validRates.map(item => ({
        cpt_code: item.cpt_code,
        rate: item.rate,
        modifier: item.modifier || ''  // Allow empty modifiers
      }));
      
      console.log('Saving line item rates:', {
        tin: currentProviderTin,
        line_items: lineItemsWithModifiers
      });

      response = await fetch('/api/rates/correct/line-items', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tin: currentProviderTin,
          line_items: lineItemsWithModifiers
        })
      });
    } else {
      // Save category corrections
      const categoryEntries = Object.entries(categoryRates);
      
      console.log('Category entries before filtering:', categoryEntries);
      
      // Filter out categories with no rate set
      const validCategories = categoryEntries.filter(([category, rateData]) => {
        const isValid = rateData && rateData.rate !== null && rateData.rate !== undefined;
        console.log('Checking category:', category, 'rateData:', rateData, 'isValid:', isValid);
        return isValid;
      });
      
      console.log('Valid categories after filtering:', validCategories);
      
      // Only validate if there are any rates entered
      const hasAnyRates = validCategories.length > 0;
      
      if (!hasAnyRates) {
        showErrorMessage('You are in the Category Correction tab but no rates have been entered. Please either:\n1. Enter rates for the categories you want to update, or\n2. Switch to the Line Item Correction tab if you want to correct individual CPT codes.');
        return;
      }
      
      const categoryData = {};
      validCategories.forEach(([category, rateData]) => {
        // Send just the rate value, not the object with rate and modifier
        categoryData[category] = rateData.rate;
      });

      console.log('Saving category rates:', {
        tin: currentProviderTin,
        category_rates: categoryData
      });
      
      response = await fetch('/api/rates/correct/category', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tin: currentProviderTin,
          category_rates: categoryData
        })
      });
    }
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to save rate corrections');
    }
    
    const result = await response.json();
    
    // Close the modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('rateCorrectionModal'));
    if (modal) {
      modal.hide();
    }
    
    // Show success message
    showSuccessMessage('Rate corrections saved successfully');
    
    // Update the UI to reflect the resolved failure
    if (currentFailureData) {
      updateFailureStatus(currentFailureData);
    }
    
  } catch (error) {
    console.error('Error saving rate corrections:', error);
    showErrorMessage(error.message || 'Failed to save rate corrections. Please try again.');
  }
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
      messagesElement.innerHTML += '<br><span class="text-success fw-bold">✓ Rate issues resolved</span>';
    }
    
    // Disable the fix button if it exists
    const fixButton = document.getElementById('fix-rate-button');
    if (fixButton) {
      fixButton.disabled = true;
      fixButton.textContent = 'Rates Fixed';
      fixButton.classList.remove('btn-primary');
      fixButton.classList.add('btn-success');
    }
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

// Attach event listeners when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
  // Attach save button click event
  const saveButton = document.getElementById('save-rate-corrections');
  if (saveButton) {
    saveButton.addEventListener('click', saveRateCorrections);
  }
}); 