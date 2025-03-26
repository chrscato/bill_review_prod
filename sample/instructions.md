# Simplified "Edit All" Functionality Instructions

This guide provides instructions for modifying the BRSystem web portal to replace individual field edit buttons with a single "Edit All" button per section.

## Overview

We'll implement the following changes:

1. Remove individual edit buttons from each field
2. Add an "Edit All" button to each section's header
3. Update the event handlers to enable editing for all fields in a section at once
4. Keep the existing save mechanism for each section

## Implementation Steps

### Step 1: Modify the createEditableField Function

Update the `createEditableField` function to remove individual edit buttons:

```javascript
function createEditableField(value, field, section, index = null) {
    const displayValue = value || 'N/A';
    const inputValue = value || '';
    const dataAttr = index !== null ? `data-index="${index}"` : '';
    
    return `
        <div class="editable-field" data-field="${field}" data-section="${section}" ${dataAttr}>
            <span class="editable-display">${displayValue}</span>
            <input type="text" 
                   class="form-control form-control-sm editable-input" 
                   value="${inputValue}"
                   style="display: none;">
        </div>
    `;
}
```

### Step 2: Modify Card Headers in displayDetails Function

Update the HTML for card headers in the `displayDetails` function to include the "Edit All" button:

```javascript
// Patient Information section
hcfaDetails.innerHTML = `
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
                <table class="table table-sm">
                    <tr>
                        <th>Name</th>
                        <td>${createEditableField(patientInfo.patient_name, 'patient_name', 'patient_info')}</td>
                    </tr>
                    <tr>
                        <th>DOB</th>
                        <td>${createEditableField(formatDOB(patientInfo.patient_dob), 'patient_dob', 'patient_info')}</td>
                    </tr>
                    <tr>
                        <th>ZIP</th>
                        <td>${createEditableField(patientInfo.patient_zip, 'patient_zip', 'patient_info')}</td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
`;

// Billing Information section - repeat same pattern
hcfaDetails.innerHTML += `
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
            <!-- Keep the same field content -->
        </div>
    </div>
`;

// Service Lines section - repeat same pattern
hcfaDetails.innerHTML += `
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
            <!-- Keep the same field content -->
        </div>
    </div>
`;
```

### Step 3: Add handleEditAllClick Function

Add a new function to handle clicking the "Edit All" button:

```javascript
/**
 * Handle clicking the "Edit All" button
 */
function handleEditAllClick(event) {
    const button = event.currentTarget;
    const section = button.dataset.section;
    
    console.log(`Edit All clicked for section: ${section}`);
    
    // Find all editable fields in this section
    const editableFields = document.querySelectorAll(`.editable-field[data-section="${section}"]`);
    
    console.log(`Found ${editableFields.length} fields to edit`);
    
    editableFields.forEach(field => {
        // Show input and hide display
        const display = field.querySelector('.editable-display');
        const input = field.querySelector('.editable-input');
        
        if (display && input) {
            display.style.display = 'none';
            input.style.display = 'block';
            
            // Store original value for potential cancel
            input.dataset.originalValue = input.value;
        }
    });
    
    // Mark all fields in this section as being edited
    editedFields.clear(); // Clear previous edits
    editableFields.forEach(field => {
        const fieldName = field.dataset.field;
        const index = field.hasAttribute('data-index') ? field.dataset.index : '';
        editedFields.add(`${section}:${fieldName}:${index}`);
    });
    
    // Hide Edit All button and show Save button
    button.style.display = 'none';
    const saveButton = document.querySelector(`.save-section[data-section="${section}"]`);
    if (saveButton) {
        saveButton.style.display = 'block';
    }
}
```

### Step 4: Update Event Listeners Setup

Update the `setupEventListeners` function to handle the new "Edit All" buttons:

```javascript
function setupEventListeners() {
    // Existing event listeners...
    
    // Add event delegation for "Edit All" buttons
    document.addEventListener('click', function(event) {
        const target = event.target;
        
        if (target.classList.contains('edit-all-btn')) {
            handleEditAllClick({ currentTarget: target });
        }
    });
}
```

### Step 5: Update the handleSaveClick Function

Make sure the save function handles reverting all fields to display mode:

```javascript
async function handleSaveClick(section) {
    showLoading();
    
    try {
        // Get current document data
        const documentData = window.currentDocumentData;
        if (!documentData) {
            throw new Error('No document data available');
        }
        
        // Deep clone to avoid modifying the original directly
        const updatedData = JSON.parse(JSON.stringify(documentData));
        
        console.log('Original data:', documentData);
        console.log('Section to update:', section);
        
        // Get all edited fields for this section
        const editableFields = document.querySelectorAll(`.editable-field[data-section="${section}"]`);
        
        // Update data based on all fields
        editableFields.forEach(field => {
            const input = field.querySelector('.editable-input');
            const display = field.querySelector('.editable-display');
            
            if (!input || !display) return;
            
            const value = input.value;
            const fieldName = field.dataset.field;
            const index = field.hasAttribute('data-index') ? parseInt(field.dataset.index) : null;
            
            console.log('Updating field:', { fieldName, value, index });
            
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
            
            // Reset display mode
            display.textContent = value || 'N/A';
            display.style.display = 'block';
            input.style.display = 'none';
        });
        
        console.log('Updated data:', updatedData);
        
        // Save changes back to server
        const response = await fetch(`/api/failures/${documentData.filename}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updatedData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showSuccess('Changes saved successfully');
            
            // Update the local data
            window.currentDocumentData = updatedData;
            
            // Reset edited fields tracking
            editedFields.clear();
            
            // Show Edit All button and hide Save button
            const editAllButton = document.querySelector(`.edit-all-btn[data-section="${section}"]`);
            const saveButton = document.querySelector(`.save-section[data-section="${section}"]`);
            
            if (editAllButton) editAllButton.style.display = 'block';
            if (saveButton) saveButton.style.display = 'none';
        } else {
            throw new Error(result.message || 'Failed to save changes');
        }
    } catch (error) {
        console.error('Error saving changes:', error);
        showError(`Failed to save changes: ${error.message}`);
    } finally {
        hideLoading();
    }
}
```

### Step 6: Add a Cancel Button (Optional)

To further improve usability, consider adding a Cancel button next to the Save button:

```javascript
// In the card header HTML
<div>
    <button class="btn btn-sm btn-outline-primary edit-all-btn" data-section="patient_info">
        Edit All
    </button>
    <button class="btn btn-sm btn-secondary cancel-all-btn" data-section="patient_info" style="display: none;">
        Cancel
    </button>
    <button class="btn btn-sm btn-primary save-section" data-section="patient_info" style="display: none;">
        Save Changes
    </button>
</div>

// Add a handleCancelAllClick function
function handleCancelAllClick(event) {
    const button = event.currentTarget;
    const section = button.dataset.section;
    
    // Find all editable fields in this section
    const editableFields = document.querySelectorAll(`.editable-field[data-section="${section}"]`);
    
    editableFields.forEach(field => {
        // Show display and hide input
        const display = field.querySelector('.editable-display');
        const input = field.querySelector('.editable-input');
        
        if (display && input) {
            // Restore original value
            input.value = input.dataset.originalValue || '';
            display.style.display = 'block';
            input.style.display = 'none';
        }
    });
    
    // Clear edited fields for this section
    editedFields.clear();
    
    // Show Edit All button and hide Cancel/Save buttons
    const editAllButton = document.querySelector(`.edit-all-btn[data-section="${section}"]`);
    const saveButton = document.querySelector(`.save-section[data-section="${section}"]`);
    const cancelButton = document.querySelector(`.cancel-all-btn[data-section="${section}"]`);
    
    if (editAllButton) editAllButton.style.display = 'block';
    if (saveButton) saveButton.style.display = 'none';
    if (cancelButton) cancelButton.style.display = 'none';
}

// Add to event listeners
if (target.classList.contains('cancel-all-btn')) {
    handleCancelAllClick({ currentTarget: target });
}

// Update the handleEditAllClick function to show the Cancel button
const cancelButton = document.querySelector(`.cancel-all-btn[data-section="${section}"]`);
if (cancelButton) {
    cancelButton.style.display = 'block';
}
```

### Step 7: Add Some Simple CSS Enhancements

Add this CSS to improve the editing experience:

```css
/* Add this to your CSS file */
.editable-field.editing {
    border: 1px solid #ddd;
    padding: 5px;
    border-radius: 4px;
    background-color: #f8f9fa;
}

.editable-input {
    width: 100%;
    margin-top: 5px;
}

.edit-all-btn, .save-section, .cancel-all-btn {
    margin-left: 5px;
}
```

## Testing the Implementation

To test your changes:

1. Start the web server
2. Load a document in the interface
3. Click the "Edit All" button for a section
4. Verify all fields in that section become editable
5. Make changes to some fields
6. Click "Save Changes" and verify the updates are saved
7. If you added the Cancel button, test that it properly reverts changes

## Common Issues and Solutions

- **Problem:** Edit All button doesn't make fields editable
  - **Solution:** Check the console for JavaScript errors and verify your selectors match the actual HTML structure

- **Problem:** Changes aren't being saved properly
  - **Solution:** Ensure the document update logic correctly builds the nested structure before saving

- **Problem:** Fields revert to their original values after saving
  - **Solution:** Verify the display elements are being updated with the new values

This implementation simplifies the editing experience by allowing users to edit all fields in a section at once, while maintaining the same underlying functionality of your existing system.