// Dashboard JavaScript for BRSystem
document.addEventListener('DOMContentLoaded', function() {
    // Fetch dashboard data
    fetchDashboardData();

    // Set up refresh button if it exists
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            this.classList.add('fa-spin');
            fetchDashboardData().finally(() => {
                this.classList.remove('fa-spin');
            });
        });
    }
});

/**
 * Show loading state
 */
function showLoading() {
    const loadingEl = document.createElement('div');
    loadingEl.id = 'loading-overlay';
    loadingEl.className = 'loading-overlay';
    loadingEl.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    document.body.appendChild(loadingEl);
}

/**
 * Hide loading state
 */
function hideLoading() {
    const loadingEl = document.getElementById('loading-overlay');
    if (loadingEl) {
        loadingEl.remove();
    }
}

/**
 * Show error message
 */
function showError(message) {
    const errorEl = document.createElement('div');
    errorEl.className = 'alert alert-danger alert-dismissible fade show';
    errorEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.querySelector('.container-fluid').prepend(errorEl);
}

/**
 * Fetch dashboard data from API
 */
async function fetchDashboardData() {
    try {
        showLoading();
        const response = await fetch('/api/dashboard');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status !== 'success') {
            throw new Error(data.message || 'Failed to load dashboard data');
        }
        
        // Update dashboard with data
        updateDashboard(data.data);
        
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
        showError('Failed to load dashboard data: ' + error.message);
    } finally {
        hideLoading();
    }
}

/**
 * Update dashboard with data
 * @param {Object} data - Dashboard data
 */
function updateDashboard(data) {
    // Update summary statistics
    document.getElementById('total-failures').textContent = data.total_failures || 0;
    document.getElementById('rate-issues').textContent = data.failure_counts.rate || 0;
    document.getElementById('unauthorized-issues').textContent = data.failure_counts.unauthorized || 0;
    document.getElementById('component-issues').textContent = data.failure_counts.component || 0;
    document.getElementById('cpt-issues').textContent = data.failure_counts.cpt || 0;
    document.getElementById('other-issues').textContent = data.failure_counts.other || 0;
    
    // Update charts
    createFailureTypeChart(data.failure_counts);
    
    // Only create network status chart if we have the data
    if (data.network_status && Object.keys(data.network_status).length > 0) {
        createNetworkStatusChart(data.network_status);
    } else {
        // Hide or clear the network status chart container
        const networkStatusChart = document.getElementById('network-status-chart');
        if (networkStatusChart) {
            networkStatusChart.innerHTML = '<div class="alert alert-info">No network status data available</div>';
        }
    }
    
    // Update recent failures table
    updateRecentFailuresTable(data.recent_failures);
    
    // Update breakdown cards
    updateBreakdownCards(data.breakdown);
}

/**
 * Create failure type chart
 * @param {Object} failureCounts - Failure counts by type
 */
function createFailureTypeChart(failureCounts) {
    const ctx = document.getElementById('failures-by-type-chart').getContext('2d');
    
    // Check if chart already exists and destroy it
    if (window.failureTypeChart) {
        window.failureTypeChart.destroy();
    }
    
    // Extract labels and data
    const labels = Object.keys(failureCounts).map(key => {
        switch(key) {
            case 'rate': return 'Rate Issues';
            case 'unauthorized': return 'Unauthorized';
            case 'component': return 'Component Bills';
            case 'cpt': return 'CPT Issues';
            case 'intent': return 'Clinical Intent';
            case 'other': return 'Other Issues';
            default: return key;
        }
    });
    const data = Object.values(failureCounts);
    
    // Define colors
    const colors = [
        '#dc3545', // danger (rate)
        '#ffc107', // warning (unauthorized)
        '#28a745', // success (component)
        '#17a2b8', // info (cpt)
        '#6f42c1', // purple (intent)
        '#6c757d'  // secondary (other)
    ];
    
    // Create chart
    window.failureTypeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Number of Failures',
                data: data,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: colors.slice(0, labels.length),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

/**
 * Create network status chart
 * @param {Object} networkStatus - Network status data
 */
function createNetworkStatusChart(networkStatus) {
    const ctx = document.getElementById('network-status-chart').getContext('2d');
    
    // Check if chart already exists and destroy it
    if (window.networkStatusChart) {
        window.networkStatusChart.destroy();
    }
    
    // Extract labels and data
    const labels = Object.keys(networkStatus);
    const data = Object.values(networkStatus);
    
    // Define colors
    const colors = [
        '#28a745', // success (in-network)
        '#ffc107', // warning (out-of-network)
        '#6c757d'  // secondary (unknown)
    ];
    
    // Create chart
    window.networkStatusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: 'white',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right'
                }
            }
        }
    });
}

/**
 * Update recent failures table
 * @param {Array} recentFailures - Recent failures data
 */
function updateRecentFailuresTable(recentFailures) {
    const tableBody = document.getElementById('recent-failures-table');
    
    if (!recentFailures || recentFailures.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="7" class="text-center">No recent failures found</td></tr>';
        return;
    }
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    // Add new rows
    recentFailures.forEach(failure => {
        const row = document.createElement('tr');
        
        // Create badge for failure type
        let badgeClass = 'bg-secondary';
        if (failure.failure_type === 'rate') badgeClass = 'bg-danger';
        if (failure.failure_type === 'unauthorized') badgeClass = 'bg-warning';
        if (failure.failure_type === 'component') badgeClass = 'bg-success';
        if (failure.failure_type === 'cpt') badgeClass = 'bg-info';
        
        // Format validation messages
        const messages = failure.validation_messages || [];
        const messagesHtml = messages.map(msg => `<div class="text-muted small">${msg}</div>`).join('');
        
        row.innerHTML = `
            <td>${failure.filename}</td>
            <td>${failure.order_id || 'N/A'}</td>
            <td>${failure.patient_name || 'N/A'}</td>
            <td>${failure.date || 'N/A'}</td>
            <td><span class="badge ${badgeClass}">${failure.failure_type}</span></td>
            <td>${messagesHtml}</td>
            <td>
                <a href="javascript:void(0)" onclick="viewFailure('${failure.filename}')" class="btn btn-sm btn-outline-primary">View</a>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
}

/**
 * View a specific failure
 * @param {string} filename - Failure filename
 */
function viewFailure(filename) {
    // Redirect to the main page with this file selected
    window.location.href = `/?file=${filename}`;
}

/**
 * Update breakdown cards
 * @param {Object} breakdown - Breakdown data
 */
function updateBreakdownCards(breakdown) {
    const container = document.getElementById('breakdown-cards');
    
    if (!breakdown || Object.keys(breakdown).length === 0) {
        container.innerHTML = '<div class="col-12"><div class="alert alert-info">No breakdown data available</div></div>';
        return;
    }
    
    // Clear existing cards
    container.innerHTML = '';
    
    // Add new cards
    Object.entries(breakdown).forEach(([category, data]) => {
        const col = document.createElement('div');
        col.className = 'col-md-4 mb-4';
        
        // Get appropriate card color and title
        let cardClass = 'bg-light';
        let title = category;
        switch(category) {
            case 'rate':
                cardClass = 'border-danger';
                title = 'Rate Issues';
                break;
            case 'unauthorized':
                cardClass = 'border-warning';
                title = 'Unauthorized Services';
                break;
            case 'component':
                cardClass = 'border-success';
                title = 'Component Billing';
                break;
            case 'cpt':
                cardClass = 'border-info';
                title = 'CPT Validation';
                break;
        }
        
        // Create card content
        let cardContent = '';
        Object.entries(data).forEach(([subcategory, count]) => {
            cardContent += `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span>${subcategory}</span>
                    <span class="badge bg-primary">${count}</span>
                </div>
            `;
        });
        
        col.innerHTML = `
            <div class="card ${cardClass}">
                <div class="card-header">
                    <h5 class="card-title mb-0">${title}</h5>
                </div>
                <div class="card-body">
                    ${cardContent}
                </div>
            </div>
        `;
        
        container.appendChild(col);
    });
} 