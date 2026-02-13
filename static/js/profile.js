/**
 * Profile management module
 * Handles profile editing functionality
 */
(function () {
    'use strict';

    // State
    var originalValues = {};
    var isSubmitting = false;

    /**
     * Enable edit mode
     */
    function enableEdit() {
        var inputs = document.querySelectorAll('.field-input');
        inputs.forEach(function (input) {
            if (input.name) {
                originalValues[input.name] = input.value;
                input.disabled = false;
            }
        });

        document.getElementById('editActions').classList.add('show');
        document.getElementById('editBtn').style.display = 'none';
    }

    /**
     * Cancel edit and restore original values
     */
    function cancelEdit() {
        var inputs = document.querySelectorAll('.field-input');
        inputs.forEach(function (input) {
            if (input.name && originalValues[input.name] !== undefined) {
                input.value = originalValues[input.name];
            }
            input.disabled = true;
        });

        document.getElementById('editActions').classList.remove('show');
        document.getElementById('editBtn').style.display = 'block';
        originalValues = {};
    }

    /**
     * Initialize the profile module
     */
    function init() {
        var form = document.getElementById('profileForm');
        if (form) {
            form.addEventListener('submit', function (e) {
                if (isSubmitting) {
                    e.preventDefault();
                    return false;
                }
                isSubmitting = true;
                var saveBtn = document.getElementById('saveBtn');
                if (saveBtn) {
                    saveBtn.disabled = true;
                    saveBtn.textContent = 'Saving...';
                }
            });
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose public API
    window.enableEdit = enableEdit;
    window.cancelEdit = cancelEdit;

})();
