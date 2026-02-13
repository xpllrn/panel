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

    // Expose to global scope
    window.getCSRFToken = getCSRFToken;
    window.sanitizeHTML = sanitizeHTML;
    window.escapeHTML = escapeHTML;
    window.showError = showError;
    window.hideError = hideError;
    window.setButtonLoading = setButtonLoading;
    window.resetButton = resetButton;
})();
