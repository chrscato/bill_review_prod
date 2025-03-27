/**
 * Rate Correction Module for BRSystem
 * Handles rate corrections for in-network providers with rate validation failures
 */

// Global variables to store current modal data
let currentProviderTin = '';
let currentFailureData = null;
let lineItemRates = [];
let categoryRates = {};
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
    "76604", "76642", "76856", "76857", "76870"
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

// Define and export the showRateCorrectionModal function immediately
window.showRateCorrectionModal = function(failure) {
    console.log('Rate correction modal function called');
    console.log('Checking if document qualifies for rate correction:', failure);
    
    // Check if this is a rate validation failure
    if (!isRateValidationFailure(failure)) {
        showErrorMessage('This document does not have any rate validation failures.');
        return;
    }
    
    // Get provider info from the correct location in the data structure
    const providerInfo = failure.database_details?.provider_details || {};
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
    document.getElementById('provider-network').textContent = providerInfo.provider_network;
    
    // Populate line items table
    populateLineItemsTable(failure);
    
    // Populate category table
    populateCategoryTable();
    
    // Reset active tab to line item correction
    const tabElement = document.getElementById('line-item-tab');
    if (tabElement) {
        const tab = new bootstrap.Tab(tabElement);
        tab.show();
    }
    
    // Show the modal
    const modalElement = document.getElementById('rateCorrectionModal');
    if (modalElement) {
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
    } else {
        console.error('Rate correction modal element not found');
        showErrorMessage('Could not find rate correction modal. Please refresh the page and try again.');
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
  
  // Check service lines first (this is where the rate data is)
  if (failure.service_lines && Array.isArray(failure.service_lines)) {
    console.log('Found service lines:', failure.service_lines);
    rates = failure.service_lines.map(item => ({
      cpt: item.cpt_code,
      description: item.description || item.proc_desc || '',
      rate: parseFloat(item.charge_amount) || 0,
      category: item.proc_category || ''
    }));
  }
  // Check direct rates array
  else if (failure.rates && Array.isArray(failure.rates)) {
    console.log('Found rates in failure.rates:', failure.rates);
    rates = failure.rates;
  }
  // Check database details
  else if (failure.database_details?.rates) {
    console.log('Found rates in database_details:', failure.database_details.rates);
    rates = failure.database_details.rates;
  }
  // Check validation results
  else if (failure.database_details?.validation_results?.rate_validation?.rates) {
    console.log('Found rates in validation results:', failure.database_details.validation_results.rate_validation.rates);
    rates = failure.database_details.validation_results.rate_validation.rates;
  }
  // Check line items
  else if (failure.line_items) {
    console.log('Found line items:', failure.line_items);
    rates = failure.line_items.map(item => ({
      cpt: item.cpt_code || item.proc_cd,
      description: item.description || item.proc_desc,
      rate: item.rate || item.amount,
      category: item.proc_category || ''
    }));
  }
  
  if (rates.length === 0) {
    console.log('No rates found in any location');
    const row = document.createElement('tr');
    row.innerHTML = '<td colspan="5" class="text-center">No rate issues found</td>';
    tableBody.appendChild(row);
    return;
  }
  
  console.log('Processing rates for display:', rates);
  
  // Add each line item to the table
  rates.forEach((rate, index) => {
    const cptCode = rate.cpt || rate.proc_cd || '';
    const description = rate.description || rate.proc_desc || '';
    const currentRate = rate.rate || rate.amount || 0;
    const currentCategory = rate.category || '';
    
    console.log('Processing rate item:', { cptCode, description, currentRate, currentCategory });
    
    // Create category dropdown
    const categorySelect = document.createElement('select');
    categorySelect.className = 'form-select category-select';
    categorySelect.dataset.index = index;
    categorySelect.dataset.cpt = cptCode;
    
    // Add default option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select Category';
    categorySelect.appendChild(defaultOption);
    
    // Add existing categories
    Object.keys(availableCategories).forEach(category => {
      const option = document.createElement('option');
      option.value = category;
      option.textContent = category;
      if (category === currentCategory) {
        option.selected = true;
      }
      categorySelect.appendChild(option);
    });
    
    // Add custom option
    const customOption = document.createElement('option');
    customOption.value = 'custom';
    customOption.textContent = 'Add Custom Category';
    categorySelect.appendChild(customOption);
    
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${cptCode}</td>
      <td class="description-cell">${description}</td>
      <td>$${currentRate.toFixed(2)}</td>
      <td>
        <input 
          type="number" 
          class="form-control rate-input" 
          data-index="${index}" 
          data-cpt="${cptCode}" 
          min="0" 
          step="0.01">
      </td>
      <td>
        <div class="category-select-container">
          ${categorySelect.outerHTML}
          <input 
            type="text" 
            class="form-control custom-category-input d-none" 
            placeholder="Enter custom category"
            data-index="${index}">
        </div>
      </td>
    `;
    tableBody.appendChild(row);
    
    // Store line item for later use
    lineItemRates.push({
      cpt_code: cptCode,
      description: description,
      rate: null,
      category: currentCategory
    });
    
    // Add event listeners for category selection
    const select = row.querySelector('.category-select');
    const customInput = row.querySelector('.custom-category-input');
    
    select.addEventListener('change', function() {
      if (this.value === 'custom') {
        customInput.classList.remove('d-none');
        customInput.focus();
      } else {
        customInput.classList.add('d-none');
        lineItemRates[index].category = this.value;
      }
    });
    
    customInput.addEventListener('input', function() {
      lineItemRates[index].category = this.value;
    });
  });
  
  // Add event listeners to rate inputs
  const rateInputs = document.querySelectorAll('.rate-input');
  rateInputs.forEach(input => {
    input.addEventListener('input', function() {
      const index = parseInt(this.dataset.index);
      const rate = parseFloat(this.value);
      
      if (!isNaN(rate) && rate >= 0) {
        this.classList.remove('is-invalid');
        lineItemRates[index].rate = rate;
      } else {
        this.classList.add('is-invalid');
        lineItemRates[index].rate = null;
      }
    });
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
  for (const [category, codes] of Object.entries(availableCategories)) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${category}</td>
      <td class="cpt-codes-cell">${codes.join(', ')}</td>
      <td>
        <input 
          type="number" 
          class="form-control rate-input category-input" 
          data-category="${category}" 
          min="0" 
          step="0.01">
      </td>
    `;
    tableBody.appendChild(row);
  }
  
  // Add event listeners to category rate inputs
  const categoryInputs = document.querySelectorAll('.category-input');
  categoryInputs.forEach(input => {
    input.addEventListener('input', function() {
      const category = this.dataset.category;
      const rate = parseFloat(this.value);
      
      if (!isNaN(rate) && rate >= 0) {
        this.classList.remove('is-invalid');
        categoryRates[category] = rate;
      } else {
        this.classList.add('is-invalid');
        delete categoryRates[category];
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
    let response;
    
    if (isLineItemActive) {
      // Save line item corrections
      const validRates = lineItemRates.filter(item => item.rate !== null);
      
      if (validRates.length === 0) {
        showErrorMessage('Please enter at least one valid rate');
        return;
      }
      
      response = await fetch('/api/rates/correct/line-items', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tin: currentProviderTin,
          line_items: validRates
        })
      });
    } else {
      // Save category corrections
      const categoryEntries = Object.entries(categoryRates);
      
      if (categoryEntries.length === 0) {
        showErrorMessage('Please enter at least one category rate');
        return;
      }
      
      const categoryData = {};
      categoryEntries.forEach(([category, rate]) => {
        categoryData[category] = rate;
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
    modal.hide();
    
    // Show success message
    showSuccessMessage('Rate corrections saved successfully');
    
    // Update the UI to reflect the resolved failure
    updateFailureStatus(currentFailureData);
    
  } catch (error) {
    console.error('Error saving rate corrections:', error);
    showErrorMessage(error.message || 'Failed to save rate corrections');
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