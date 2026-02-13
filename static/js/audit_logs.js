/**
 * Audit Logs module
 * Handles log detail modal display
 */
(function () {
    'use strict';

    var logModal;

    function init() {
        logModal = document.getElementById('logModal');

        window.addEventListener('click', function (event) {
            if (event.target === logModal) closeLogModal();
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') closeLogModal();
        });
    }

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value || '-';
    }

    function showLogDetail(logId) {
        fetch('/audit-logs/' + logId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data.success) {
                    alert(data.error || 'Failed to load log details');
                    return;
                }

                var log = data.log;
                setText('log-created-at', log.created_at);
                setText('log-user', log.user_name + (log.user_username ? ' (' + log.user_username + ')' : ''));
                setText('log-action', log.action_display);
                setText('log-entity-type', log.entity_type_display);
                setText('log-entity-id', log.entity_id ? String(log.entity_id) : 'N/A');
                setText('log-description', log.description);
                setText('log-ip', log.ip_address || 'N/A');

                logModal.classList.add('show');
            })
            .catch(function (err) {
                console.error('Error loading log:', err);
                alert('Failed to load log details');
            });
    }

    function closeLogModal() {
        if (logModal) logModal.classList.remove('show');
    }

    // Expose to global scope
    window.showLogDetail = showLogDetail;
    window.closeLogModal = closeLogModal;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
