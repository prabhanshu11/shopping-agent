// Shopping Agent - Main JavaScript
// Note: Most functionality is in page-specific scripts in templates

// Utility function for safe text element creation
function createTextElement(tag, text, className) {
    const el = document.createElement(tag);
    el.textContent = text;
    if (className) el.className = className;
    return el;
}

// Global error handler
window.addEventListener('error', function(e) {
    console.error('Global error:', e.message);
});

// Fetch wrapper with error handling
async function safeFetch(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

// Notification helper
function showNotification(message, type = 'info') {
    // Simple alert for now - can be replaced with toast library
    alert(message);
}

// Format currency
function formatCurrency(amount, currency = 'INR') {
    return currency + ' ' + Number(amount).toFixed(2);
}

// Format date
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString();
}

// Format datetime
function formatDateTime(dateString) {
    return new Date(dateString).toLocaleString();
}

// Debounce function for search
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

console.log('Shopping Agent loaded');
