// Initialize search functionality
document.addEventListener('DOMContentLoaded', function() {
    setupSearchEventListeners();
});

// Setup search event listeners
function setupSearchEventListeners() {
    const searchButton = document.getElementById('searchButton');
    const firstNameInput = document.getElementById('firstNameSearch');
    const lastNameInput = document.getElementById('lastNameSearch');
    const dosInput = document.getElementById('dosSearch');
    const monthsRangeSelect = document.getElementById('monthsRange');
    
    // Search button click
    searchButton.addEventListener('click', performSearch);
    
    // Enter key in inputs
    [firstNameInput, lastNameInput, dosInput].forEach(input => {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    });
}

// Perform the search
function performSearch() {
    const firstName = document.getElementById('firstNameSearch').value.trim();
    const lastName = document.getElementById('lastNameSearch').value.trim();
    const dos = document.getElementById('dosSearch').value.trim();
    const monthsRange = document.getElementById('monthsRange').value;
    
    // Validate inputs
    if (!firstName && !lastName) {
        showSearchStatus('Please enter at least a first or last name', 'warning');
        return;
    }
    
    // Show loading status
    showSearchStatus('Searching...', 'info');
    document.getElementById('matchResults').innerHTML = '';
    document.getElementById('matchCount').textContent = '0';
    
    // Perform the search
    fetch('/mapping/api/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            first_name: firstName,
            last_name: lastName,
            dos_date: dos,
            months_range: monthsRange
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showSearchStatus(data.error, 'danger');
            return;
        }
        
        displaySearchResults(data.results);
    })
    .catch(error => {
        console.error('Error performing search:', error);
        showSearchStatus('Error performing search', 'danger');
    });
}

// Display search results
function displaySearchResults(results) {
    const matchResults = document.getElementById('matchResults');
    const matchCount = document.getElementById('matchCount');
    
    // Update count
    matchCount.textContent = results.length;
    matchCount.className = `badge bg-${results.length > 0 ? 'success' : 'secondary'}`;
    
    // Clear previous results
    matchResults.innerHTML = '';
    
    if (results.length === 0) {
        showSearchStatus('No matches found', 'warning');
        return;
    }
    
    // Show success status
    showSearchStatus(`${results.length} matches found`, 'success');
    
    // Display results
    results.forEach(result => {
        const matchItem = document.createElement('div');
        matchItem.className = 'match-item';
        matchItem.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>${result.patient_name}</strong><br>
                    <small class="text-muted">DOB: ${result.date_of_birth}</small>
                </div>
                <div class="text-end">
                    <small class="text-muted">Order ID: ${result.order_id}</small><br>
                    <small class="text-muted">FileMaker: ${result.filemaker_id}</small>
                </div>
            </div>
        `;
        
        // Add click handler
        matchItem.addEventListener('click', () => {
            // Update form fields
            document.getElementById('orderIdInput').value = result.order_id;
            document.getElementById('filemakerInput').value = result.filemaker_id;
            
            // Update selected state
            document.querySelectorAll('.match-item').forEach(item => {
                item.classList.remove('selected');
            });
            matchItem.classList.add('selected');
        });
        
        matchResults.appendChild(matchItem);
    });
}

// Show search status message
function showSearchStatus(message, type) {
    const searchStatus = document.getElementById('searchStatus');
    searchStatus.className = `alert alert-${type} mb-2`;
    searchStatus.textContent = message;
} 