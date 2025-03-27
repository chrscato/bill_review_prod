# Database-Side Editable Functionality Enhancement for BRSystem Web Portal

This document provides step-by-step instructions for enhancing the FileMaker/database side of the web portal with the same editable functionality as the JSON side. This enhancement will allow users to edit database records directly from the UI, with updates saving back to the database rather than to JSON files.

## Overview

**Important Note: This enhancement builds upon the existing "Edit All" functionality. Do not remove or undo any of the previous JSON-side editing capabilities - we are adding parallel functionality for the database side.**

The main tasks are:
1. Add a new Flask endpoint for updating database records
2. Add a new database service method to handle database updates
3. Enhance the frontend to make database fields editable
4. Implement save functionality for database updates

## Backend Changes

### Step 1: Add a New API Endpoint in `web/app.py`

Add this new endpoint to handle database updates:

```python
@app.route('/api/order/<order_id>', methods=['PUT'])
def update_order_details(order_id):
    """API endpoint to update order details in the database."""
    try:
        logger.info(f"Updating database details for order: {order_id}")
        updated_data = request.get_json()
        
        success = db_service.update_order_details(order_id, updated_data)
        
        if not success:
            logger.error(f"Failed to update order: {order_id}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to update order: {order_id}'
            }), 500
            
        logger.info(f"Successfully updated order: {order_id}")
        return jsonify({
            'status': 'success',
            'message': 'Order updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
```

### Step 2: Add New Method to `DatabaseService` in `core/services/database.py`

Add this method to handle the actual database updates:

```python
def update_order_details(self, order_id: str, data: Dict) -> bool:
    """
    Update order details, provider details, and line items in the database.
    
    Args:
        order_id: Order ID to update
        data: Dictionary containing updated data
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = self.connect_db()
        
        try:
            # Start a transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Update order details
            if "order_details" in data:
                order_updates = []
                order_values = []
                
                for field, value in data["order_details"].items():
                    if field != "Order_ID":  # Don't update the primary key
                        order_updates.append(f"{field} = ?")
                        order_values.append(value)
                
                if order_updates:
                    order_query = f"""
                    UPDATE orders 
                    SET {', '.join(order_updates)}
                    WHERE Order_ID = ?
                    """
                    order_values.append(order_id)
                    conn.execute(order_query, order_values)
            
            # Update provider details if provider_id is present
            if "provider_details" in data and "provider_id" in data.get("order_details", {}):
                provider_id = data["order_details"]["provider_id"]
                provider_updates = []
                provider_values = []
                
                for field, value in data["provider_details"].items():
                    # Map field names to database column names
                    db_field = field
                    if field == "provider_name":
                        db_field = "Name"
                    elif field == "network_status":
                        db_field = "Provider Status"
                    elif field == "provider_network":
                        db_field = "Provider Network"
                    
                    provider_updates.append(f'"{db_field}" = ?')
                    provider_values.append(value)
                
                if provider_updates:
                    provider_query = f"""
                    UPDATE providers
                    SET {', '.join(provider_updates)}
                    WHERE PrimaryKey = ?
                    """
                    provider_values.append(provider_id)
                    conn.execute(provider_query, provider_values)
            
            # Update line items
            if "line_items" in data:
                for item in data["line_items"]:
                    # Skip if no id is provided
                    if "id" not in item:
                        continue
                        
                    item_id = item["id"]
                    item_updates = []
                    item_values = []
                    
                    for field, value in item.items():
                        if field != "id":  # Don't update the primary key
                            item_updates.append(f"{field} = ?")
                            item_values.append(value)
                    
                    if item_updates:
                        item_query = f"""
                        UPDATE line_items
                        SET {', '.join(item_updates)}
                        WHERE id = ? AND Order_ID = ?
                        """
                        item_values.extend([item_id, order_id])
                        conn.execute(item_query, item_values)
            
            # Commit the transaction
            conn.commit()
            logger.info(f"Successfully updated database for Order ID: {order_id}")
            return True
            
        except Exception as e:
            # Rollback on error
            conn.rollback()
            logger.error(f"Error updating order details for {order_id}: {str(e)}")
            return False
            
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Database connection error while updating order {order_id}: {str(e)}")
        return False
```

## Frontend Changes

### Step 3: Update the `displayDetails` Function in `web/static/js/main.js`

Replace the existing database details rendering code with this enhanced version that adds editable fields:

```javascript
// Inside the displayDetails function, replace the existing dbDetailsPanel code:

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
  `;
} else {
  dbDetailsPanel.innerHTML = `
    <div class="alert alert-warning">
      Database details not available for this order.
    </div>
  `;
}
```

### Step 4: Add Database Save Functionality to Event Handlers

Add a new function in `web/static/js/main.js` to handle database save operations:

```javascript
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
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updatedData)
    });
    
    const result = await response.json();
    
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
```

### Step 5: Update the Event Handlers to Support Database Edits

Modify the click event handler for the save section button in the `setupEventListeners` function to handle database sections:

```javascript
// Inside the document.addEventListener('click') handler in setupEventListeners, 
// find where you handle the save-section buttons and modify:

// Save section button clicked
if (target.classList.contains('save-section')) {
  event.preventDefault();
  
  const section = target.dataset.section;
  
  // Check if this is a database section (starts with db_)
  if (section.startsWith('db_')) {
    saveDbSection(section);
  } else {
    // Handle JSON saves as before
    // (Your existing save logic for JSON fields)
    // ...
  }
}
```

## Testing the Implementation

After implementing these changes, you should test the following:

1. View a failure document with database details
2. Click "Edit All" for a database section
3. Modify some fields
4. Click "Save Changes"
5. Verify that the changes are saved to the database
6. Reload the page and verify the changes persist

## Troubleshooting Common Issues

- **Fields Not Becoming Editable**: Check that your `createEditableField` function is properly generating editable fields. Check the console for any errors.
- **Save Button Not Appearing**: Ensure the `edit-all-btn` and `save-section` buttons have the correct `data-section` attributes.
- **Database Updates Not Working**: Check the server logs for SQL errors. Ensure the field names match the database column names.
- **Line Item Updates Not Working**: Verify that the `data-item-id` attribute is correctly added to each row, and that the item ID is correctly passed to the server.

## Best Practices

1. Always use database transactions to ensure data integrity
2. Handle errors gracefully and provide clear feedback to users
3. Use debug logging to help diagnose issues
4. Remember that this enhancement builds on existing functionality, so maintain compatibility with the JSON editing side

This implementation provides a seamless editing experience that mirrors the existing JSON-side editing functionality but applies it to database records, allowing for a consistent user experience regardless of which data source is being edited.