/**
 * Utility functions for the admin portal
 * ES5 IIFE pattern - exposed via window.*
 */
(function () {
    'use strict';

    /**
     * Get CSRF token from cookie
     */
    function getCSRFToken() {
        var name = 'csrftoken';
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Sanitize HTML to prevent XSS attacks
     */
    function sanitizeHTML(str) {
        if (!str) return '';
        var temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    }

    /**
     * Escape HTML entities
     */
    function escapeHTML(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Show error message to user
     */
    function showError(message, container) {
        if (!container) return;
        container.textContent = message;
        container.style.display = 'block';
    }

    /**
     * Hide error message
     */
    function hideError(container) {
        if (!container) return;
        container.textContent = '';
        container.style.display = 'none';
    }

    /**
     * Disable button and show loading state
     */
    function setButtonLoading(button, loadingText) {
        if (!button) return '';
        var originalText = button.textContent;
        button.disabled = true;
        button.textContent = loadingText || 'Loading...';
        return originalText;
    }

    /**
     * Re-enable button and restore original text
     */
    function resetButton(button, originalText) {
        if (!button) return;
        button.disabled = false;
        button.textContent = originalText;
    }

    /**
     * Format number in Indian numbering system (lakhs and crores)
     * Examples: 1,00,000 | 10,00,000 | 1,00,00,000
     */
    function formatIndianNumber(num) {
        if (num === null || num === undefined || num === '') return '0';
        
        var number = parseFloat(num);
        if (isNaN(number)) return '0';
        
        // Handle negative numbers
        var isNegative = number < 0;
        number = Math.abs(number);
        
        // Split into integer and decimal parts
        var parts = number.toFixed(2).split('.');
        var integerPart = parts[0];
        var decimalPart = parts[1];
        
        // Indian numbering: last 3 digits, then groups of 2
        var lastThree = integerPart.substring(integerPart.length - 3);
        var otherNumbers = integerPart.substring(0, integerPart.length - 3);
        
        if (otherNumbers !== '') {
            lastThree = ',' + lastThree;
        }
        
        var result = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree;
        
        // Add decimal part
        if (decimalPart && decimalPart !== '00') {
            result += '.' + decimalPart;
        }
        
        return (isNegative ? '-' : '') + result;
    }

    /**
     * Format currency in Indian Rupees
     * Example: ₹1,00,000.00
     */
    function formatCurrency(amount) {
        return '₹' + formatIndianNumber(amount);
    }

    // Expose to global scope
    window.getCSRFToken = getCSRFToken;
    window.sanitizeHTML = sanitizeHTML;
    window.escapeHTML = escapeHTML;
    window.showError = showError;
    window.hideError = hideError;
    window.setButtonLoading = setButtonLoading;
    window.resetButton = resetButton;
    window.formatIndianNumber = formatIndianNumber;
    window.formatCurrency = formatCurrency;
})();
