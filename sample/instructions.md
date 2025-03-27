Bill Resolved Feature Implementation Instructions
This document provides structured instructions for implementing a "Bill Resolved" feature in the Healthcare Bill Review System. This feature allows users to mark a failed bill as resolved and move it back to the staging directory.
1. Add a new route in app.py
Add this endpoint to your web/app.py file to handle the "Bill Resolved" action:
pythonCopy@app.route('/api/failures/<filename>/resolve', methods=['POST'])
def resolve_failure(filename):
    """API endpoint to mark a failure as resolved and move it back to staging."""
    try:
        logger.info(f"Resolving failure: {filename}")
        
        # Construct paths
        fails_path = settings.FAILS_PATH / filename
        staging_path = settings.JSON_PATH / filename
        
        if not fails_path.exists():
            logger.error(f"Failure file not found: {fails_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        # Read the failure file
        with open(fails_path, 'r') as f:
            data = json.load(f)
            
        # Remove validation messages
        if 'validation_messages' in data:
            del data['validation_messages']
            
        # Write the modified data to the staging directory
        with open(staging_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Remove the file from the fails directory
        fails_path.unlink()
            
        logger.info(f"Successfully resolved failure: {filename}")
        return jsonify({
            'status': 'success',
            'message': 'Failure resolved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resolving failure: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
2. Add the resolveBill function to main.js
Add this function to your web/static/js/main.js file:
javascriptCopy/**
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
3. Add a Bill Resolved button to the UI
Add this code to your web/static/js/main.js file in the displayDetails function, where you add other action buttons (near where you add the "Fix Rate Issues" button):
javascriptCopy// Add the Bill Resolved button
const resolveButton = document.createElement('button');
resolveButton.className = 'btn btn-success mt-3 ms-2';
resolveButton.id = 'resolve-bill-button';
resolveButton.textContent = 'Bill Resolved';
resolveButton.onclick = function() {
    if (confirm('Are you sure you want to mark this bill as resolved? This will move the file back to staging.')) {
        resolveBill(jsonDetails);
    }
};

// Add button after validation messages
const messagesElement = hcfaDetails.querySelector('.card-body');
if (messagesElement) {
    messagesElement.appendChild(resolveButton);
}
4. Add CSS styles for the button
Add these styles to your web/static/css/style.css file:
cssCopy#resolve-bill-button {
    background-color: #28a745;
    color: white;
    font-weight: bold;
    transition: all 0.2s;
}

#resolve-bill-button:hover {
    background-color: #218838;
    transform: translateY(-2px);
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}
Implementation Notes

This feature adds a "Bill Resolved" button to the UI for failed bills
When clicked, it removes the validation messages from the JSON file
The file is moved from the fails directory back to the staging directory
The UI is updated to reflect that the bill has been resolved
The bill is removed from the list of failures in the UI

Make sure your settings.JSON_PATH points to the correct staging directory:
CopyC:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VA