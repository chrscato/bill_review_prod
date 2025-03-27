// Global variables
let currentDocument = null;
let allDocuments = [];
let allFailures = [];
let uniqueFailureTypes = new Set();

// Application state management
const appState = {
  currentDocument: null,
  originalData: null,
  editedFields: new Map(), // Map of field paths to new values
  
  // Initialize with document
  setDocument(document) {
    this.currentDocument = document;
    this.originalData = JSON.parse(JSON.stringify(document)); // Deep clone
    this.editedFields.clear();
  },
  
  // Track edited field
  updateField(path, value) {
    this.editedFields.set(path, value);
    document.getElementById('saveAllChanges').disabled = false;
  },
  
  // Remove edited field
  removeField(path) {
    this.editedFields.delete(path);
    if (this.editedFields.size === 0) {
      document.getElementById('saveAllChanges').disabled = true;
    }
  },
  
  // Check if has edits
  hasEdits() {
    return this.editedFields.size > 0;
  },
  
  // Generate updated document
  getUpdatedDocument() {
    const updated = JSON.parse(JSON.stringify(this.originalData));
    
    for (const [path, value] of this.editedFields) {
      const parts = path.split('.');
      let current = updated;
      
      // Navigate to the right nesting level
      for (let i = 0; i < parts.length - 1; i++) {
        const part = parts[i];
        if (part.includes('[')) {
          // Handle array access like service_lines[0]
          const name = part.substring(0, part.indexOf('['));
          const index = parseInt(part.substring(part.indexOf('[') + 1, part.indexOf(']')));
          
          if (!current[name]) current[name] = [];
          while (current[name].length <= index) current[name].push({});
          current = current[name][index];
        } else {
          if (!current[part]) current[part] = {};
          current = current[part];
        }
      }
      
      // Get the final property name
      const lastPart = parts[parts.length - 1];
      
      // Special handling for modifiers which should be an array
      if (lastPart === 'modifiers' && typeof value === 'string') {
        current[lastPart] = value.split(',').map(m => m.trim()).filter(Boolean);
      } else {
        // Set the value at the final property
        current[lastPart] = value;
      }
    }
    
    return updated;
  }
};

// Debug mode flag
const DEBUG = true;

// Enhanced logging function
function debug(...args) {
    if (DEBUG) {
        console.log(`[${new Date().toISOString()}]`, ...args);
    }
}

// Error logging with stack traces
function logError(message, error) {
    console.error(`[${new Date().toISOString()}] ERROR: ${message}`, error);
    if (error && error.stack) {
        console.error('Stack trace:', error.stack);
    }
}

/**
 * Safely get a nested property from an object
 */
function getNestedProperty(obj, path, defaultValue = 'N/A') {
    if (!obj) return defaultValue;
    
    const keys = path.split('.');
    let value = obj;
    
    for (const key of keys) {
        if (value === null || value === undefined || typeof value !== 'object') {
            return defaultValue;
        }
        value = value[key];
    }
    
    return value === null || value === undefined ? defaultValue : value;
}

/**
 * Format a value for display, handling various data types
 */
function formatDisplayValue(value, defaultValue = 'N/A') {
    if (value === null || value === undefined || value === '') {
        return defaultValue;
    }
    
    if (Array.isArray(value)) {
        return value.join(', ');
    }
    
    return String(value);
}

/**
 * Clean and sanitize input values
 */
function sanitizeInputValue(value) {
    if (value === null || value === undefined) {
        return '';
    }
    
    // Convert to string and trim
    return String(value).trim();
}

/**
 * Safely get a value from a nested path in an object
 */
function getValueByPath(obj, path) {
  if (!obj || !path) return null;
  
  const parts = path.split('.');
  let current = obj;
  
  for (const part of parts) {
    if (part.includes('[')) {
      // Handle array access like service_lines[0]
      const name = part.substring(0, part.indexOf('['));
      const index = parseInt(part.substring(part.indexOf('[') + 1, part.indexOf(']')));
      
      if (!current[name] || !current[name][index]) return null;
      current = current[name][index];
    } else {
      if (!current[part]) return null;
      current = current[part];
    }
  }
  
  return current;
}

/**
 * Format a value for display
 */
function formatForDisplay(value) {
  if (value === null || value === undefined || value === '') return 'N/A';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

/**
 * Clean a value for an input field
 */
function formatForInput(value) {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

/**
 * Create an editable field component
 */
function createEditableField(value, path) {
  const displayValue = formatForDisplay(value);
  const inputValue = formatForInput(value);
  const fieldId = `field-${path.replace(/\./g, '-').replace(/\[|\]/g, '-')}`;
  
  return `
    <div class="editable-field" data-path="${path}">
      <div class="display-value" id="${fieldId}-display">${displayValue}</div>
      <div class="edit-container" style="display: none;">
        <input type="text" 
               class="form-control form-control-sm editable-input" 
               id="${fieldId}-input" 
               value="${inputValue}" 
               data-original-value="${inputValue}"
               data-path="${path}">
      </div>
    </div>
  `;
}

// Define the click handler function globally
function handleEditClick(event) {
    event.preventDefault(); // Prevent any default button behavior
    event.stopPropagation(); // Prevent event bubbling
    
    const button = event.currentTarget;
    const field = button.dataset.field;
    const section = button.dataset.section;
    const index = button.hasAttribute('data-index') ? button.dataset.index : null;
    
    debug('Edit button clicked:', { field, section, index });
    
    // Find the editable field container - look in the same td as the button
    const td = button.closest('td');
    if (!td) {
        logError('Table cell not found');
        return;
    }
    
    // Find the editable field container within the same td
    const editableField = td.querySelector('.editable-field');
    if (!editableField) {
        logError('Editable field container not found');
        return;
    }
    
    const input = editableField.querySelector('.editable-input');
    const display = editableField.querySelector('.editable-display');
    
    if (!input || !display) {
        logError('Input or display element not found', { input, display });
        return;
    }
    
    const isCurrentlyEditing = editableField.classList.contains('editing');
    debug('Current editing state:', isCurrentlyEditing);
    
    if (!isCurrentlyEditing) {
        // Show input and hide display
        editableField.classList.add('editing');
        
        // Reset input value to match display (in case there were unsaved changes)
        input.value = display.textContent === 'N/A' ? '' : display.textContent;
        
        input.focus(); // Focus the input field
        
        editedFields.add(`${section}:${field}:${index || ''}`);
        
        // Make sure save button is visible
        const sectionSaveButton = document.querySelector(`.save-section[data-section="${section}"]`);
        if (sectionSaveButton) {
            debug('Showing save button for section:', section);
            sectionSaveButton.style.display = 'block';
        } else {
            logError(`Save button not found for section: ${section}`);
        }
    } else {
        // Hide input and show display
        editableField.classList.remove('editing');
        
        button.textContent = 'Edit';
        button.classList.remove('btn-outline-danger');
        button.classList.add('btn-outline-primary');
        
        // Remove from edited fields
        editedFields.delete(`${section}:${field}:${index || ''}`);
        
        // Check if any other fields in this section are still being edited
        const hasSectionEdits = Array.from(editedFields).some(f => f.startsWith(section + ':'));
        
        // Hide save button if no more edits in this section
        const sectionSaveButton = document.querySelector(`.save-section[data-section="${section}"]`);
        if (sectionSaveButton && !hasSectionEdits) {
            debug('Hiding save button for section:', section);
            sectionSaveButton.style.display = 'none';
        }
    }
}

// Add this function after handleEditClick function
async function handleSaveClick(section) {
    showLoading();
    
    try {
        // Get current document data from appState
        const documentData = appState.currentDocument;
        if (!documentData) {
            throw new Error('No document data available');
        }
        
        // Deep clone to avoid modifying the original directly
        const updatedData = JSON.parse(JSON.stringify(documentData));
        
        debug('Original data:', documentData);
        debug('Section to update:', section);
        
        // Get all edited fields for this section
        const editedFieldsForSection = Array.from(document.querySelectorAll(`.editable-field.editing`))
            .filter(field => {
                const input = field.querySelector('.editable-input');
                return input && input.dataset.path.startsWith(section);
            });
        
        debug('Fields to update:', editedFieldsForSection.length);
        
        // Update data based on edited fields
        editedFieldsForSection.forEach(field => {
            const input = field.querySelector('.editable-input');
            const value = input.value;
            const path = input.dataset.path;
            const pathParts = path.split('.');
            const fieldName = pathParts[pathParts.length - 1];
            const index = pathParts.length > 2 ? parseInt(pathParts[1]) : null;
            
            debug('Updating field:', { fieldName, value, index });
            
            if (index !== null && !isNaN(index)) {
                // Handle array items (like service_lines)
                if (!updatedData[section]) {
                    updatedData[section] = [];
                }
                
                // Ensure array has enough elements
                while (updatedData[section].length <= index) {
                    updatedData[section].push({});
                }
                
                // Handle special cases like modifiers which are arrays
                if (fieldName === 'modifiers') {
                    updatedData[section][index][fieldName] = value.split(',')
                        .map(m => m.trim())
                        .filter(m => m);
                } else {
                    updatedData[section][index][fieldName] = value;
                }
            } else {
                // Handle direct properties
                if (!updatedData[section]) {
                    updatedData[section] = {};
                }
                updatedData[section][fieldName] = value;
            }
            
            // Reset edit state
            field.classList.remove('editing');
            const display = field.querySelector('.display-value');
            if (display) {
                display.textContent = value || 'N/A';
                display.style.display = 'block';
            }
            field.querySelector('.edit-container').style.display = 'none';
        });
        
        debug('Updated data:', updatedData);
        
        // Save changes back to server
        const response = await fetch(`/api/failures/${currentDocument.filename}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updatedData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showSuccess('Changes saved successfully');
            
            // Update the appState with new data
            appState.setDocument(updatedData);
            
            // Hide save button and show edit all button
            const saveButton = document.querySelector(`.save-section[data-section="${section}"]`);
            const editAllButton = document.querySelector(`.edit-all-btn[data-section="${section}"]`);
            if (saveButton) saveButton.style.display = 'none';
            if (editAllButton) editAllButton.style.display = 'block';
        } else {
            throw new Error(result.message || 'Failed to save changes');
        }
    } catch (error) {
        logError('Error saving changes:', error);
        showError(`Failed to save changes: ${error.message}`);
    } finally {
        hideLoading();
    }
}

/**
 * Save all changes to the server
 */
async function saveAllChanges() {
  if (!appState.hasEdits()) return;
  
  showLoading();
  
  try {
    const updatedDocument = appState.getUpdatedDocument();
    
    // Send to server
    const response = await fetch(`/api/failures/${currentDocument.filename}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updatedDocument)
    });
    
    const result = await response.json();
    
    if (result.status === 'success') {
      // Update state with saved document
      appState.setDocument(updatedDocument);
      
      // Show success message
      showSuccess('All changes saved successfully');
      
      // Disable save button
      document.getElementById('saveAllChanges').disabled = true;
    } else {
      throw new Error(result.message || 'Failed to save changes');
    }
  } catch (error) {
    console.error('Error saving changes:', error);
    showError(`Failed to save: ${error.message}`);
  } finally {
    hideLoading();
  }
}

/**
 * Save changes to the database
 */
async function saveDbSection(section) {
  showLoading();
  
  try {
    if (!currentDocument || !window.dbData) {
      throw new Error('No document or database data available');
    }
    
    const orderId = window.dbData.order_details?.Order_ID;
    if (!orderId) {
      throw new Error('No Order ID available');
    }
    
    // Create a copy of the original data
    const updatedData = JSON.parse(JSON.stringify(window.dbData));
    
    // Get the real section name without the db_ prefix
    const realSection = section.substring(3); // Remove 'db_' prefix
    
    debug('Saving database section:', { section, realSection, orderId });
    debug('Original data:', window.dbData);
    
    // Get all edited fields for this section
    const editableFields = document.querySelectorAll(`.editable-field[data-path^="${section}"]`);
    debug(`Found ${editableFields.length} editable fields for section ${section}`);
    
    // Update data based on all fields
    editableFields.forEach(field => {
      const path = field.dataset.path;
      const pathParts = path.split('.');
      const input = field.querySelector('input');
      const display = field.querySelector('.display-value');
      
      if (!input || !display) return;
      
      const newValue = input.value;
      debug('Updating field:', { path, newValue });
      
      // Path format is like: db_order_details.PatientName
      // Or for line items: db_line_items.0.CPT
      if (pathParts.length === 2) {
        // Simple field like db_order_details.PatientName
        const fieldName = pathParts[1];
        updatedData[realSection][fieldName] = newValue;
      } else if (pathParts.length === 3 && realSection === 'line_items') {
        // Line items field like db_line_items.0.CPT
        const index = parseInt(pathParts[1]);
        const fieldName = pathParts[2];
        
        // Make sure we have the correct item ID for database update
        const row = document.querySelector(`tr[data-item-id]:nth-child(${index + 1})`);
        const itemId = row?.dataset.itemId;
        
        if (itemId && updatedData[realSection][index]) {
          updatedData[realSection][index][fieldName] = newValue;
          updatedData[realSection][index]['id'] = itemId;
          debug('Updated line item:', { index, fieldName, newValue, itemId });
        } else {
          debug('Could not find line item to update:', { index, itemId });
        }
      }
      
      // Exit edit mode
      field.classList.remove('editing');
      display.textContent = newValue || 'N/A';
      display.style.display = 'block';
      field.querySelector('.edit-container').style.display = 'none';
    });
    
    debug('Sending updated data to server:', updatedData);
    
    // Send update to the server
    const response = await fetch(`/api/order/${orderId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(updatedData)
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      debug('Server error response:', errorData);
      throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
    }
    
    const result = await response.json();
    debug('Server success response:', result);
    
    if (result.status === 'success') {
      showSuccess('Database updated successfully');
      
      // Update the local data
      window.dbData = updatedData;
      
      // Show Edit All button and hide Save button
      const editAllButton = document.querySelector(`.edit-all-btn[data-section="${section}"]`);
      const saveButton = document.querySelector(`.save-section[data-section="${section}"]`);
      
      if (editAllButton) editAllButton.style.display = 'block';
      if (saveButton) saveButton.style.display = 'none';
    } else {
      throw new Error(result.message || 'Failed to update database');
    }
  } catch (error) {
    logError('Error saving to database:', error);
    showError(`Failed to save to database: ${error.message}`);
  } finally {
    hideLoading();
  }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    // Remove dynamic script loading since it's already in HTML
    loadFailures();
    setupEventListeners();
});

/**
 * Mark a bill as resolved and move it back to staging
 * @param {Object} failure - The failure data object
 */
async function resolveBill(failure) {
    if (!failure || !failure.filename) {
        showError('Invalid failure data');
        return;
    }
    
    try {
        showLoading();
        const filename = failure.filename;
        
        const response = await fetch(`/api/failures/${filename}/resolve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        showSuccess('Bill has been resolved and moved to staging');
        
        // Remove the failure from the document list
        const failureElement = document.querySelector(`.document-item[data-filename="${filename}"]`);
        if (failureElement) {
            failureElement.remove();
        }
        
        // Clear the details panels
        document.getElementById('hcfaDetails').innerHTML = '<div class="alert alert-success">Bill has been resolved and moved to staging.</div>';
        document.getElementById('dbDetails').innerHTML = '';
        
        // Remove from currentDocument
        currentDocument = null;
        
    } catch (error) {
        console.error('Error resolving bill:', error);
        showError(`Failed to resolve bill: ${error.message}`);
    } finally {
        hideLoading();
    }
}

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

    // Add document-level event delegation for editable fields
    document.addEventListener('click', function(event) {
        const target = event.target;
        
        // Edit All button clicked
        if (target.classList.contains('edit-all-btn')) {
            event.preventDefault();
            
            const section = target.dataset.section;
            const editableFields = document.querySelectorAll(`.editable-field[data-path^="${section}"]`);
            
            // Enter edit mode for all fields in the section
            editableFields.forEach(field => {
                field.classList.add('editing');
                field.querySelector('.display-value').style.display = 'none';
                field.querySelector('.edit-container').style.display = 'block';
            });
            
            // Hide Edit All button and show Save button
            target.style.display = 'none';
            const saveButton = document.querySelector(`.save-section[data-section="${section}"]`);
            if (saveButton) {
                saveButton.style.display = 'block';
            }
            
            // Focus the first input
            const firstInput = editableFields[0]?.querySelector('input');
            if (firstInput) firstInput.focus();
        }
        
        // Save section button clicked
        if (target.classList.contains('save-section')) {
            event.preventDefault();
            
            const section = target.dataset.section;
            
            // Check if this is a database section (starts with db_)
            if (section.startsWith('db_')) {
                saveDbSection(section);
            } else {
                // Handle JSON saves
                handleSaveClick(section);
            }
        }
        
        // Global save button clicked
        if (target.id === 'saveAllChanges') {
            event.preventDefault();
            saveAllChanges();
        }
    });
    
    // Handle keyboard events in input fields
    document.addEventListener('keydown', function(event) {
        const target = event.target;
        
        // Only handle events in our inputs
        if (!target.matches('.editable-field input')) return;
        
        if (event.key === 'Enter') {
            // Find the section this input belongs to
            const field = target.closest('.editable-field');
            const path = field.dataset.path;
            const section = path.split('.')[0];
            
            // Find and click the save button for this section
            const saveButton = document.querySelector(`.save-section[data-section="${section}"]`);
            if (saveButton) saveButton.click();
        } else if (event.key === 'Escape') {
            // Find the section this input belongs to
            const field = target.closest('.editable-field');
            const path = field.dataset.path;
            const section = path.split('.')[0];
            
            // Find and click the edit all button for this section
            const editAllButton = document.querySelector(`.edit-all-btn[data-section="${section}"]`);
            if (editAllButton) editAllButton.click();
        }
    });
}

// Load validation failures
async function loadFailures() {
    try {
        showLoading();
        const response = await fetch('/api/failures');
        if (!response.ok) {
            throw new Error('Failed to fetch failures');
        }
        
        const result = await response.json();
        console.log('API Response:', result); // Log the API response
        
        if (result.status !== 'success') {
            throw new Error(`Failed to load failures: ${result.message}`);
        }
        
        // Store all failures
        allFailures = result.data;
        console.log('Stored failures:', allFailures); // Log stored failures
        
        // Log sample of failures for debugging
        if (allFailures.length > 0) {
            console.log('Sample failure structure:', {
                validation_messages: allFailures[0].validation_messages,
                database_details: allFailures[0].database_details,
                provider_details: allFailures[0].database_details?.provider_details
            });
        }
        
        // Extract unique failure types
        uniqueFailureTypes.clear();
        allFailures.forEach(failure => {
            const types = extractFailureTypes(failure);
            types.forEach(type => uniqueFailureTypes.add(type));
        });
        
        // Update status filter dropdown
        updateStatusFilter(allFailures);
        
        // Apply current filter
        const statusFilter = document.getElementById('statusFilter');
        const filteredFailures = filterFailuresByStatus(allFailures, statusFilter.value);
        
        // Log filtered results
        console.log('Filtered failures:', filteredFailures);
        
        // Display filtered failures
        displayFailures(filteredFailures);
        
    } catch (error) {
        console.error('Error loading failures:', error);
        showError('Failed to load failures');
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
                <div class="text-truncate">
                    ${doc.filename}
                </div>
                <span class="status-badge ${doc.status === 'critical' ? 'status-critical' : 'status-non-critical'}">
                    ${doc.status}
                </span>
            </div>
        `;
        div.onclick = () => selectDocument(doc);
        container.appendChild(div);
    });
}

// Select a document
async function selectDocument(doc) {
    try {
        showLoading();
        currentDocument = doc;
        
        // Update active state in document list
        document.querySelectorAll('.document-item').forEach(item => {
            item.classList.remove('active');
        });
        event.currentTarget.classList.add('active');
        
        // Fetch document details
        const [jsonResponse, dbResponse] = await Promise.all([
            fetch(`/api/failures/${doc.filename}`),
            fetch(`/api/order/${doc.order_id}`)
        ]);
        
        if (!jsonResponse.ok) {
            throw new Error('Failed to fetch document details');
        }
        
        const jsonResult = await jsonResponse.json();
        if (jsonResult.status !== 'success') {
            throw new Error(`Failed to load JSON details: ${jsonResult.message}`);
        }
        
        let dbData = null;
        if (dbResponse.ok) {
            const dbResult = await dbResponse.json();
            if (dbResult.status === 'success') {
                dbData = dbResult.data;
            } else {
                console.warn(`Database details not available: ${dbResult.message}`);
            }
        } else {
            console.warn('Failed to load database details');
        }
        
        // Display the details
        displayDetails(jsonResult.data, dbData);
        
        // Wait a short moment to ensure all scripts are loaded
        setTimeout(() => {
            // Create a button container div
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'd-flex gap-2 mt-3';
            buttonContainer.id = 'action-buttons';

            // Add the Fix Rates button for in-network providers
            const fixButton = document.createElement('button');
            fixButton.className = 'btn btn-primary';
            fixButton.id = 'fix-rate-button';
            fixButton.textContent = 'Fix Rate Issues';
            fixButton.onclick = function() {
                console.log('Rate correction button clicked');
                console.log('showRateCorrectionModal available:', typeof window.showRateCorrectionModal === 'function');
                
                // Check if the rate correction function exists
                if (typeof window.showRateCorrectionModal === 'function') {
                    // Call the rate correction modal function with the current document data
                    window.showRateCorrectionModal(jsonResult.data);
                } else {
                    console.error('Rate correction function not found');
                    showErrorMessage('Error: Rate correction functionality not loaded. Please refresh the page and try again.');
                }
            };

            // Add the OTA Rates button for out-of-network providers
            const otaButton = document.createElement('button');
            otaButton.className = 'btn btn-secondary';
            otaButton.id = 'add-ota-button';
            otaButton.textContent = 'Add OTA Rates';
            otaButton.onclick = function() {
                console.log('OTA correction button clicked');
                console.log('showOTACorrectionModal available:', typeof window.showOTACorrectionModal === 'function');
                
                // Check if the OTA correction function exists
                if (typeof window.showOTACorrectionModal === 'function') {
                    // Call the OTA correction modal function with both JSON and database data
                    const combinedData = {
                        ...jsonResult.data,
                        database_details: dbData
                    };
                    window.showOTACorrectionModal(combinedData);
                } else {
                    console.error('OTA correction function not found');
                    showErrorMessage('Error: OTA correction functionality not loaded. Please refresh the page and try again.');
                }
            };

            // Add the Bill Resolved button
            const resolveButton = document.createElement('button');
            resolveButton.className = 'btn btn-success';
            resolveButton.id = 'resolve-bill-button';
            resolveButton.textContent = 'Bill Resolved';
            resolveButton.onclick = function() {
                if (confirm('Are you sure you want to mark this bill as resolved? This will move the file back to staging.')) {
                    resolveBill({
                        filename: doc.filename
                    });
                }
            };

            // Add all buttons to the container
            buttonContainer.appendChild(fixButton);
            buttonContainer.appendChild(otaButton);
            buttonContainer.appendChild(resolveButton);

            // Add the button container after validation messages
            const messagesElement = hcfaDetails.querySelector('.card-body');
            if (messagesElement) {
                messagesElement.appendChild(buttonContainer);
            }
        }, 100);
        
    } catch (error) {
        console.error('Error selecting document:', error);
        showError('Failed to load document details');
    } finally {
        hideLoading();
    }
}

/**
 * Display document details with editable fields
 */
function displayDetails(jsonDetails, dbDetails) {
  if (!jsonDetails) {
    showError('No document details available');
    return;
  }
  
  // Store the document in application state
  appState.setDocument(jsonDetails);
  
  // Render HCFA details with editable fields
  const hcfaDetails = document.getElementById('hcfaDetails');
  if (!hcfaDetails) return;

  // Format DOB to remove newlines and extra spaces
  const formatDOB = (dob) => {
    if (!dob) return null;
    return dob.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
  };

  // Get patient info
  const patientInfo = jsonDetails.patient_info || {};
  const billingInfo = jsonDetails.billing_info || {};
  const serviceLines = jsonDetails.service_lines || [];

  // Create service lines HTML
  const serviceLinesHtml = serviceLines.map((line, index) => `
    <tr>
      <td>${createEditableField(line.date_of_service, `service_lines.${index}.date_of_service`)}</td>
      <td>${createEditableField(line.cpt_code, `service_lines.${index}.cpt_code`)}</td>
      <td>${createEditableField(line.modifiers, `service_lines.${index}.modifiers`)}</td>
      <td>${createEditableField(line.units, `service_lines.${index}.units`)}</td>
      <td>${createEditableField(line.diagnosis_pointer, `service_lines.${index}.diagnosis_pointer`)}</td>
      <td>${createEditableField(line.place_of_service, `service_lines.${index}.place_of_service`)}</td>
      <td>${createEditableField(line.charge_amount, `service_lines.${index}.charge_amount`)}</td>
    </tr>
  `).join('');

  hcfaDetails.innerHTML = `
    <div class="card mb-4">
      <div class="card-header">
        <h6 class="mb-0">Validation Messages</h6>
      </div>
      <div class="card-body">
        <pre class="validation-message">${(jsonDetails.validation_messages || []).join('\n')}</pre>
      </div>
    </div>

    <div class="card mb-4">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h6 class="mb-0">Patient Information</h6>
        <div>
          <button class="btn btn-sm btn-outline-primary edit-all-btn" data-section="patient_info">
            Edit All
          </button>
          <button class="btn btn-sm btn-primary save-section" data-section="patient_info" style="display: none;">
            Save Changes
          </button>
        </div>
      </div>
      <div class="card-body">
        <div class="table-responsive">
          <table class="table">
            <tbody>
              <tr>
                <th style="width: 200px;">Name</th>
                <td>${createEditableField(patientInfo.patient_name, 'patient_info.patient_name')}</td>
              </tr>
              <tr>
                <th>DOB</th>
                <td>${createEditableField(formatDOB(patientInfo.patient_dob), 'patient_info.patient_dob')}</td>
              </tr>
              <tr>
                <th>ZIP</th>
                <td>${createEditableField(patientInfo.patient_zip, 'patient_info.patient_zip')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    
    <div class="card mb-4">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h6 class="mb-0">Service Lines</h6>
        <div>
          <button class="btn btn-sm btn-outline-primary edit-all-btn" data-section="service_lines">
            Edit All
          </button>
          <button class="btn btn-sm btn-primary save-section" data-section="service_lines" style="display: none;">
            Save Changes
          </button>
        </div>
      </div>
      <div class="card-body">
        <div class="table-responsive">
          <table class="table">
            <thead>
              <tr>
                <th style="width: 120px;">Date of Service</th>
                <th style="width: 100px;">CPT</th>
                <th style="width: 150px;">Modifier</th>
                <th style="width: 80px;">Units</th>
                <th style="width: 100px;">Diagnosis</th>
                <th style="width: 120px;">Place of Service</th>
                <th style="width: 120px;">Charge Amount</th>
              </tr>
            </thead>
            <tbody>
              ${serviceLinesHtml}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="card mb-4">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h6 class="mb-0">Billing Information</h6>
        <div>
          <button class="btn btn-sm btn-outline-primary edit-all-btn" data-section="billing_info">
            Edit All
          </button>
          <button class="btn btn-sm btn-primary save-section" data-section="billing_info" style="display: none;">
            Save Changes
          </button>
        </div>
      </div>
      <div class="card-body">
        <div class="table-responsive">
          <table class="table">
            <tbody>
              <tr>
                <th style="width: 200px;">Provider Name</th>
                <td>${createEditableField(billingInfo.billing_provider_name, 'billing_info.billing_provider_name')}</td>
              </tr>
              <tr>
                <th>Provider NPI</th>
                <td>${createEditableField(billingInfo.billing_provider_npi, 'billing_info.billing_provider_npi')}</td>
              </tr>
              <tr>
                <th>Provider TIN</th>
                <td>${createEditableField(billingInfo.billing_provider_tin, 'billing_info.billing_provider_tin')}</td>
              </tr>
              <tr>
                <th>Total Charge</th>
                <td>${createEditableField(billingInfo.total_charge, 'billing_info.total_charge')}</td>
              </tr>
              <tr>
                <th>Account Number</th>
                <td>${createEditableField(billingInfo.patient_account_no, 'billing_info.patient_account_no')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  // Display DB details if available
  const dbDetailsPanel = document.getElementById('dbDetails');
  if (dbDetails) {
    // Initialize dbData
    window.dbData = dbDetails;
    
    // Render order details section
    const orderDetails = dbDetails.order_details || {};
    const providerDetails = dbDetails.provider_details || {};
    const lineItems = dbDetails.line_items || [];
    
    dbDetailsPanel.innerHTML = `
      <div class="card mb-4">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h6 class="mb-0">Order Details</h6>
          <div>
            <button class="btn btn-sm btn-outline-primary edit-all-btn" data-section="db_order_details">
              Edit All
            </button>
            <button class="btn btn-sm btn-primary save-section" data-section="db_order_details" style="display: none;">
              Save Changes
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table">
              <tbody>
                <tr>
                  <th style="width: 200px;">Order ID</th>
                  <td>${orderDetails.Order_ID || 'N/A'}</td>
                </tr>
                <tr>
                  <th>FileMaker Record</th>
                  <td>${createEditableField(orderDetails.FileMaker_Record_Number, 'db_order_details.FileMaker_Record_Number')}</td>
                </tr>
                <tr>
                  <th>Patient Name</th>
                  <td>${createEditableField(orderDetails.PatientName, 'db_order_details.PatientName')}</td>
                </tr>
                <tr>
                  <th>Patient DOB</th>
                  <td>${createEditableField(orderDetails.Patient_DOB, 'db_order_details.Patient_DOB')}</td>
                </tr>
                <tr>
                  <th>Patient ZIP</th>
                  <td>${createEditableField(orderDetails.Patient_Zip, 'db_order_details.Patient_Zip')}</td>
                </tr>
                <tr>
                  <th>Order Type</th>
                  <td>${createEditableField(orderDetails.Order_Type, 'db_order_details.Order_Type')}</td>
                </tr>
                <tr>
                  <th>Bundle Type</th>
                  <td>${createEditableField(orderDetails.bundle_type, 'db_order_details.bundle_type')}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      
      <div class="card mb-4">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h6 class="mb-0">Line Items</h6>
          <div>
            <button class="btn btn-sm btn-outline-primary edit-all-btn" data-section="db_line_items">
              Edit All
            </button>
            <button class="btn btn-sm btn-primary save-section" data-section="db_line_items" style="display: none;">
              Save Changes
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table">
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
                ${lineItems.map((item, index) => `
                  <tr data-item-id="${item.id}">
                    <td>${createEditableField(item.DOS, `db_line_items.${index}.DOS`)}</td>
                    <td>${createEditableField(item.CPT, `db_line_items.${index}.CPT`)}</td>
                    <td>${createEditableField(item.Modifier, `db_line_items.${index}.Modifier`)}</td>
                    <td>${createEditableField(item.Units, `db_line_items.${index}.Units`)}</td>
                    <td>${createEditableField(item.Description, `db_line_items.${index}.Description`)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h6 class="mb-0">Provider Details</h6>
          <div>
            <button class="btn btn-sm btn-outline-primary edit-all-btn" data-section="db_provider_details">
              Edit All
            </button>
            <button class="btn btn-sm btn-primary save-section" data-section="db_provider_details" style="display: none;">
              Save Changes
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table">
              <tbody>
                <tr>
                  <th style="width: 200px;">Provider Name</th>
                  <td>${createEditableField(providerDetails.provider_name, 'db_provider_details.provider_name')}</td>
                </tr>
                <tr>
                  <th>NPI</th>
                  <td>${createEditableField(providerDetails.npi, 'db_provider_details.npi')}</td>
                </tr>
                <tr>
                  <th>TIN</th>
                  <td>${createEditableField(providerDetails.tin, 'db_provider_details.tin')}</td>
                </tr>
                <tr>
                  <th>Network Status</th>
                  <td>${createEditableField(providerDetails.network_status, 'db_provider_details.network_status')}</td>
                </tr>
                <tr>
                  <th>Provider Network</th>
                  <td>${createEditableField(providerDetails.provider_network, 'db_provider_details.provider_network')}</td>
                </tr>
                <tr>
                  <th>Billing Name</th>
                  <td>${createEditableField(providerDetails.billing_name, 'db_provider_details.billing_name')}</td>
                </tr>
                <tr>
                  <th>Billing Address</th>
                  <td>${createEditableField(providerDetails.billing_address_1, 'db_provider_details.billing_address_1')}</td>
                </tr>
                <tr>
                  <th>Billing City</th>
                  <td>${createEditableField(providerDetails.billing_address_city, 'db_provider_details.billing_address_city')}</td>
                </tr>
                <tr>
                  <th>Billing State</th>
                  <td>${createEditableField(providerDetails.billing_address_state, 'db_provider_details.billing_address_state')}</td>
                </tr>
                <tr>
                  <th>Billing ZIP</th>
                  <td>${createEditableField(providerDetails.billing_address_postal_code, 'db_provider_details.billing_address_postal_code')}</td>
                </tr>
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
  
  // Add global save button
  const saveButton = document.createElement('button');
  saveButton.id = 'saveAllChanges';
  saveButton.className = 'btn btn-primary';
  saveButton.textContent = 'Save All Changes';
  saveButton.disabled = true;
  document.body.appendChild(saveButton);
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

// Function to extract unique failure types from validation messages
function extractFailureTypes(failure) {
    const types = new Set();
    
    if (failure.validation_messages) {
        failure.validation_messages.forEach(msg => {
            // Look for failure type indicators in messages
            if (msg.includes('Validation failed with')) {
                // Extract failure types from the message
                const matches = msg.match(/([A-Za-z]+)\s+Validation\s+Failed/g);
                if (matches) {
                    matches.forEach(match => {
                        const type = match.split(' ')[0]; // Get the first word (e.g., "RATE" from "RATE Validation Failed")
                        types.add(type);
                    });
                }
            }
        });
    }
    
    return types;
}

// Function to update the status filter dropdown
function updateStatusFilter(failures) {
    const statusFilter = document.getElementById('statusFilter');
    const currentValue = statusFilter.value; // Store current selection
    
    // Clear existing options except the first one
    while (statusFilter.options.length > 1) {
        statusFilter.remove(1);
    }
    
    // Get unique failure types from all failures
    const uniqueTypes = new Set();
    
    // Log the first few failures for debugging
    console.log('Sample failure structure:', failures.slice(0, 3));
    
    failures.forEach(failure => {
        // Check validation_messages
        if (failure.validation_messages) {
            failure.validation_messages.forEach(msg => {
                console.log('Processing message:', msg);
                
                // Look for rate, line items, and intent validation messages
                if (msg.toLowerCase().includes('rate')) {
                    uniqueTypes.add('RATE');
                    console.log('Found rate in message:', msg);
                }
                if (msg.includes('LINE_ITEMS Validation Failed') || 
                    msg.includes('Line Items Validation Failed') ||
                    msg.toLowerCase().includes('line items validation failed')) {
                    uniqueTypes.add('LINE_ITEMS');
                    console.log('Found line items in message:', msg);
                }
                if (msg.includes('INTENT Validation Failed') || 
                    msg.includes('Intent Validation Failed') ||
                    msg.toLowerCase().includes('intent validation failed') ||
                    msg.toLowerCase().includes('intent mismatch')) {
                    uniqueTypes.add('INTENT');
                    console.log('Found intent in message:', msg);
                }
            });
        }
    });
    
    // Add OTA option
    uniqueTypes.add('OTA');
    
    // Log the unique types for debugging
    console.log('Unique failure types:', Array.from(uniqueTypes));
    
    // Add unique failure types to dropdown
    uniqueTypes.forEach(type => {
        const option = document.createElement('option');
        option.value = type.toLowerCase();
        option.textContent = type;
        statusFilter.appendChild(option);
    });
    
    // Restore previous selection if it still exists
    if (currentValue) {
        statusFilter.value = currentValue;
    }
    
    // Log the final dropdown state
    console.log('Dropdown options:', Array.from(statusFilter.options).map(opt => opt.text));
}

// Function to filter failures based on status
function filterFailuresByStatus(failures, selectedStatus) {
    if (!selectedStatus || selectedStatus === 'all') {
        return failures;
    }
    
    return failures.filter(failure => {
        if (!failure.validation_messages) return false;
        
        // Check for OTA filter
        if (selectedStatus.toLowerCase() === 'ota') {
            console.log('Checking OTA filter for failure:', failure);
            
            // Must have rate validation failure
            const hasRateFailure = failure.validation_messages.some(msg => {
                const isRate = msg.includes('RATE Validation Failed') || 
                       msg.includes('Rate validation failed') ||
                       msg.toLowerCase().includes('rate validation failed');
                console.log('Rate failure check:', { msg, isRate });
                return isRate;
            });
            
            // Must be out of network
            const networkStatus = failure.database_details?.provider_details?.network_status;
            const isOutOfNetwork = networkStatus === 'Out of Network';
            console.log('Network status check:', { networkStatus, isOutOfNetwork });
            
            const matches = hasRateFailure && isOutOfNetwork;
            console.log('OTA filter result:', { hasRateFailure, isOutOfNetwork, matches });
            
            return matches;
        }
        
        // Check for rate validation messages
        if (selectedStatus.toLowerCase() === 'rate') {
            return failure.validation_messages.some(msg => {
                return msg.includes('RATE Validation Failed') || 
                       msg.includes('Rate validation failed') ||
                       msg.toLowerCase().includes('rate validation failed');
            });
        }
        
        // Check for line items validation messages
        if (selectedStatus.toLowerCase() === 'line_items') {
            return failure.validation_messages.some(msg => {
                return msg.includes('LINE_ITEMS Validation Failed') || 
                       msg.includes('Line Items Validation Failed') ||
                       msg.toLowerCase().includes('line items validation failed');
            });
        }
        
        // Check for intent validation messages
        if (selectedStatus.toLowerCase() === 'intent') {
            return failure.validation_messages.some(msg => {
                return msg.includes('INTENT Validation Failed') || 
                       msg.includes('Intent Validation Failed') ||
                       msg.toLowerCase().includes('intent validation failed') ||
                       msg.toLowerCase().includes('intent mismatch');
            });
        }
        
        // For other status types, check failure_types
        if (!failure.failure_types) return false;
        return failure.failure_types.includes(selectedStatus.toUpperCase());
    });
}

// Function to display failures in the document list
function displayFailures(failures) {
    const container = document.getElementById('documentList');
    container.innerHTML = '';

    if (!failures || failures.length === 0) {
        container.innerHTML = '<div class="p-2 text-center text-muted">No documents found</div>';
        return;
    }

    failures.forEach(failure => {
        const div = document.createElement('div');
        div.className = 'document-item';
        div.dataset.filename = failure.filename || '';
        
        // Create status badges for each failure type
        const statusBadges = [];
        
        // Check validation messages for different failure types
        if (failure.validation_messages) {
            failure.validation_messages.forEach(msg => {
                const msgLower = msg.toLowerCase();
                
                // Rate validation failures
                if (msgLower.includes('rate validation failed') || 
                    msgLower.includes('rate issue') ||
                    msgLower.includes('rate problem')) {
                    statusBadges.push('<span class="badge bg-danger">RATE</span>');
                }
                
                // Line items validation failures
                if (msgLower.includes('line items validation failed') || 
                    msgLower.includes('line items issue') ||
                    msgLower.includes('line items problem')) {
                    statusBadges.push('<span class="badge bg-danger">LINE_ITEMS</span>');
                }
                
                // Intent validation failures
                if (msgLower.includes('intent validation failed') || 
                    msgLower.includes('intent issue') ||
                    msgLower.includes('intent mismatch')) {
                    statusBadges.push('<span class="badge bg-danger">INTENT</span>');
                }
                
                // Bundle validation failures
                if (msgLower.includes('bundle validation failed') || 
                    msgLower.includes('bundle issue') ||
                    msgLower.includes('bundle problem')) {
                    statusBadges.push('<span class="badge bg-warning">BUNDLE</span>');
                }
                
                // Modifier validation failures
                if (msgLower.includes('modifier validation failed') || 
                    msgLower.includes('modifier issue') ||
                    msgLower.includes('invalid modifier')) {
                    statusBadges.push('<span class="badge bg-warning">MODIFIER</span>');
                }
                
                // Units validation failures
                if (msgLower.includes('units validation failed') || 
                    msgLower.includes('units issue') ||
                    msgLower.includes('invalid units')) {
                    statusBadges.push('<span class="badge bg-warning">UNITS</span>');
                }
                
                // CPT validation failures
                if (msgLower.includes('cpt validation failed') || 
                    msgLower.includes('cpt issue') ||
                    msgLower.includes('invalid cpt')) {
                    statusBadges.push('<span class="badge bg-warning">CPT</span>');
                }
                
                // Diagnosis validation failures
                if (msgLower.includes('diagnosis validation failed') || 
                    msgLower.includes('diagnosis issue') ||
                    msgLower.includes('invalid diagnosis')) {
                    statusBadges.push('<span class="badge bg-warning">DIAGNOSIS</span>');
                }
                
                // Provider validation failures
                if (msgLower.includes('provider validation failed') || 
                    msgLower.includes('provider issue') ||
                    msgLower.includes('invalid provider')) {
                    statusBadges.push('<span class="badge bg-warning">PROVIDER</span>');
                }
                
                // Patient validation failures
                if (msgLower.includes('patient validation failed') || 
                    msgLower.includes('patient issue') ||
                    msgLower.includes('invalid patient')) {
                    statusBadges.push('<span class="badge bg-warning">PATIENT</span>');
                }
                
                // Date validation failures
                if (msgLower.includes('date validation failed') || 
                    msgLower.includes('date issue') ||
                    msgLower.includes('invalid date')) {
                    statusBadges.push('<span class="badge bg-warning">DATE</span>');
                }
                
                // Amount validation failures
                if (msgLower.includes('amount validation failed') || 
                    msgLower.includes('amount issue') ||
                    msgLower.includes('invalid amount')) {
                    statusBadges.push('<span class="badge bg-warning">AMOUNT</span>');
                }
                
                // Network validation failures
                if (msgLower.includes('network validation failed') || 
                    msgLower.includes('network issue') ||
                    msgLower.includes('invalid network')) {
                    statusBadges.push('<span class="badge bg-info">NETWORK</span>');
                }
            });
        }
        
        // Add any other failure types from the failure_types array
        if (failure.failure_types) {
            failure.failure_types.forEach(type => {
                // Only add if not already added from validation messages
                if (!statusBadges.some(badge => badge.includes(type))) {
                    const badgeClass = type === 'NETWORK' ? 'bg-info' : 
                                     (type === 'RATE' || type === 'LINE_ITEMS' || type === 'INTENT') ? 'bg-danger' : 'bg-warning';
                    statusBadges.push(`<span class="badge ${badgeClass}">${type}</span>`);
                }
            });
        }
        
        // Get patient name from the data
        const patientName = failure.patient_info?.patient_name || 
                          failure.patient_name || 
                          'Unknown Patient';
        
        // Create the HTML with patient name and badges
        div.innerHTML = `
            <div class="d-flex flex-column">
                <div class="text-truncate">
                    ${patientName}
                </div>
                <div class="d-flex flex-wrap">
                    ${statusBadges.join('')}
                </div>
            </div>
        `;
        
        // Add click handler
        div.onclick = () => selectDocument(failure);
        container.appendChild(div);
    });
}