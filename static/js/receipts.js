/**
 * Receipts management module
 * Handles receipt creation, viewing, printing, member search, and dropdowns
 */
(function () {
    'use strict';

    // State
    var isAddingReceipt = false;
    var searchTimeout = null;

    // DOM Elements (cached on init)
    var receiptModal, addReceiptModal;

    /**
     * Initialize the receipts module
     */
    function init() {
        // Cache modal elements
        receiptModal = document.getElementById('receiptModal');
        addReceiptModal = document.getElementById('addReceiptModal');

        // Set up event listeners
        setupEventListeners();
    }

    /**
     * Set up global event listeners
     */
    function setupEventListeners() {
        // Close modals on outside click
        window.addEventListener('click', function (event) {
            if (event.target === receiptModal) closeReceiptModal();
            if (event.target === addReceiptModal) closeAddReceiptModal();

            // Close dropdowns when clicking outside
            if (!event.target.matches('.kebab-menu')) {
                document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
                    menu.classList.remove('show');
                });
            }

            // Close member search results when clicking outside
            var memberSelector = document.querySelector('.member-selector');
            if (memberSelector && !memberSelector.contains(event.target)) {
                var results = document.getElementById('receipt-member-results');
                if (results) results.style.display = 'none';
            }
        });

        // Close modals on Escape key
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeReceiptModal();
                closeAddReceiptModal();
            }
        });

        // Member search input with debounce
        var memberSearchInput = document.getElementById('receipt-member-search');
        if (memberSearchInput) {
            memberSearchInput.addEventListener('input', function () {
                var query = this.value.trim();
                if (searchTimeout) clearTimeout(searchTimeout);

                if (query.length < 2) {
                    var results = document.getElementById('receipt-member-results');
                    if (results) results.style.display = 'none';
                    return;
                }

                searchTimeout = setTimeout(function () {
                    searchMembers(query);
                }, 300);
            });
        }
    }

    /**
     * Format currency in INR
     */
    function formatCurrency(amount) {
        var num = parseFloat(amount);
        if (isNaN(num)) return '0.00';
        return new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    }

    /**
     * Show receipt details modal
     */
    function showReceiptModal(receiptId) {
        fetch('/receipts/' + receiptId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    var receipt = data.receipt;

                    // Receipt header
                    document.getElementById('modal-receipt-number').textContent = receipt.receipt_number;
                    document.getElementById('modal-receipt-date').textContent = receipt.created_at || receipt.created_date || '-';
                    document.getElementById('modal-payment-mode').textContent = receipt.payment_mode_display || '-';

                    // Update title based on transaction type
                    var titleEl = document.getElementById('modal-receipt-title');
                    if (titleEl) {
                        var typeUpper = (receipt.transaction_type || '').toUpperCase();
                        if (typeUpper === 'CREDIT') {
                            titleEl.textContent = 'CREDIT RECEIPT';
                        } else if (typeUpper === 'DEBIT') {
                            titleEl.textContent = 'DEBIT RECEIPT';
                        } else {
                            titleEl.textContent = 'RECEIPT';
                        }
                    }

                    // Member details
                    document.getElementById('modal-member-name').textContent = receipt.member_name || '-';
                    document.getElementById('modal-member-id').textContent = receipt.member_id || '-';
                    document.getElementById('modal-member-mobile').textContent = receipt.member_mobile || '-';
                    document.getElementById('modal-member-address').textContent = receipt.member_address || '-';

                    // Account details
                    document.getElementById('modal-account-number').textContent = receipt.account_number || '-';
                    document.getElementById('modal-account-type').textContent = receipt.account_type_display || '-';

                    // Transaction details
                    document.getElementById('modal-transaction-type').textContent = receipt.transaction_type_display || '-';
                    document.getElementById('modal-amount').textContent = '\u20B9 ' + formatCurrency(receipt.amount);
                    document.getElementById('modal-balance-after').textContent = '\u20B9 ' + formatCurrency(receipt.balance_after);

                    // Reference number (show/hide)
                    var refRow = document.getElementById('modal-reference-row');
                    var refEl = document.getElementById('modal-reference');
                    if (receipt.reference_number) {
                        refEl.textContent = receipt.reference_number;
                        refRow.style.display = '';
                    } else {
                        refRow.style.display = 'none';
                    }

                    // Description (show/hide)
                    var descSection = document.getElementById('modal-description-section');
                    var descEl = document.getElementById('modal-description');
                    if (receipt.description) {
                        descEl.textContent = receipt.description;
                        descSection.style.display = '';
                    } else {
                        descSection.style.display = 'none';
                    }

                    // Remarks (show/hide)
                    var remarksSection = document.getElementById('modal-remarks-section');
                    var remarksEl = document.getElementById('modal-remarks');
                    if (receipt.remarks) {
                        remarksEl.textContent = receipt.remarks;
                        remarksSection.style.display = '';
                    } else {
                        remarksSection.style.display = 'none';
                    }

                    // Created by
                    document.getElementById('modal-created-by').textContent = receipt.created_by_name || '-';

                    receiptModal.classList.add('show');
                } else {
                    alert('Error loading receipt: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading receipt: ' + error);
            });
    }

    /**
     * Close receipt view modal
     */
    function closeReceiptModal() {
        if (receiptModal) receiptModal.classList.remove('show');
    }

    /**
     * Show add receipt modal
     */
    function showAddReceiptModal() {
        var form = document.getElementById('addReceiptForm');
        if (form) form.reset();

        var errorDiv = document.getElementById('add-receipt-error');
        if (errorDiv) errorDiv.style.display = 'none';

        var memberSearch = document.getElementById('receipt-member-search');
        if (memberSearch) memberSearch.value = '';

        var memberId = document.getElementById('receipt-member-id');
        if (memberId) memberId.value = '';

        var results = document.getElementById('receipt-member-results');
        if (results) results.style.display = 'none';

        // Reset account dropdown
        var accountSelect = document.getElementById('receipt-account-select');
        if (accountSelect) {
            accountSelect.innerHTML = '<option value="">Select member first...</option>';
            accountSelect.disabled = true;
        }

        var btn = document.getElementById('addReceiptBtn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Create Receipt';
        }

        isAddingReceipt = false;
        addReceiptModal.classList.add('show');
    }

    /**
     * Close add receipt modal
     */
    function closeAddReceiptModal() {
        if (addReceiptModal) addReceiptModal.classList.remove('show');
    }

    /**
     * Create a new receipt
     */
    function addReceipt() {
        if (isAddingReceipt) return;

        var form = document.getElementById('addReceiptForm');
        var formData = new FormData(form);
        var errorDiv = document.getElementById('add-receipt-error');
        var btn = document.getElementById('addReceiptBtn');

        // Validate member selected
        if (!formData.get('user_id')) {
            errorDiv.textContent = 'Please select a member';
            errorDiv.style.display = 'block';
            return;
        }

        // Validate account selected
        if (!formData.get('account_id')) {
            errorDiv.textContent = 'Please select an account';
            errorDiv.style.display = 'block';
            return;
        }

        // Validate transaction type
        if (!formData.get('transaction_type')) {
            errorDiv.textContent = 'Please select a transaction type';
            errorDiv.style.display = 'block';
            return;
        }

        // Validate amount
        var amount = parseFloat(formData.get('amount'));
        if (!amount || amount <= 0) {
            errorDiv.textContent = 'Please enter a valid amount';
            errorDiv.style.display = 'block';
            return;
        }

        errorDiv.style.display = 'none';
        isAddingReceipt = true;
        btn.disabled = true;
        btn.textContent = 'Creating...';

        fetch('/receipts/add/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
            },
            body: formData
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    window.location.reload();
                } else {
                    errorDiv.textContent = data.error || 'Error creating receipt';
                    errorDiv.style.display = 'block';
                    isAddingReceipt = false;
                    btn.disabled = false;
                    btn.textContent = 'Create Receipt';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isAddingReceipt = false;
                btn.disabled = false;
                btn.textContent = 'Create Receipt';
            });
    }

    /**
     * Search members for autocomplete
     */
    function searchMembers(query) {
        fetch('/api/members/search/?q=' + encodeURIComponent(query))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                var resultsDiv = document.getElementById('receipt-member-results');
                if (!resultsDiv) return;

                if (data.results && data.results.length > 0) {
                    var html = '';
                    data.results.forEach(function (member) {
                        var display = escapeHTML(member.full_name || member.username);
                        if (member.member_id) {
                            display += ' (' + escapeHTML(member.member_id) + ')';
                        }
                        html += '<div class="member-selector-item" data-id="' + escapeHTML(String(member.id)) + '" data-name="' + escapeHTML(member.full_name || member.username) + '">' + display + '</div>';
                    });
                    resultsDiv.innerHTML = html;
                    resultsDiv.style.display = 'block';

                    // Attach click handlers to results
                    resultsDiv.querySelectorAll('.member-selector-item').forEach(function (item) {
                        item.addEventListener('click', function () {
                            var memberId = this.getAttribute('data-id');
                            var memberName = this.getAttribute('data-name');
                            selectMember(memberId, memberName);
                        });
                    });
                } else {
                    resultsDiv.innerHTML = '<div class="member-selector-empty">No members found</div>';
                    resultsDiv.style.display = 'block';
                }
            })
            .catch(function (error) {
                console.error('Error searching members:', error);
            });
    }

    /**
     * Select a member and load their accounts
     */
    function selectMember(memberId, memberName) {
        // Set hidden input and search field
        document.getElementById('receipt-member-id').value = memberId;
        document.getElementById('receipt-member-search').value = memberName;

        var resultsDiv = document.getElementById('receipt-member-results');
        if (resultsDiv) resultsDiv.style.display = 'none';

        // Load member accounts for cascading dropdown
        var accountSelect = document.getElementById('receipt-account-select');
        accountSelect.innerHTML = '<option value="">Loading accounts...</option>';
        accountSelect.disabled = true;

        fetch('/api/members/' + memberId + '/accounts/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success && data.accounts.length > 0) {
                    var html = '<option value="">Select account...</option>';
                    data.accounts.forEach(function (account) {
                        html += '<option value="' + escapeHTML(String(account.id)) + '">'
                            + escapeHTML(account.account_number)
                            + ' (' + escapeHTML(account.account_type_display) + ')'
                            + ' - \u20B9' + escapeHTML(account.balance)
                            + '</option>';
                    });
                    accountSelect.innerHTML = html;
                    accountSelect.disabled = false;
                } else {
                    accountSelect.innerHTML = '<option value="">No active accounts found</option>';
                    accountSelect.disabled = true;
                }
            })
            .catch(function (error) {
                accountSelect.innerHTML = '<option value="">Error loading accounts</option>';
                accountSelect.disabled = true;
                console.error('Error loading accounts:', error);
            });
    }

    /**
     * Toggle dropdown menu
     */
    function toggleDropdown(event, receiptId) {
        event.stopPropagation();

        document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
            if (menu.id !== 'dropdown-' + receiptId) {
                menu.classList.remove('show');
            }
        });

        document.getElementById('dropdown-' + receiptId).classList.toggle('show');
    }

    /**
     * Print a specific receipt (opens modal first, then prints)
     */
    function printReceipt(event, receiptId) {
        event.stopPropagation();

        // Close dropdown
        var dropdown = document.getElementById('dropdown-' + receiptId);
        if (dropdown) dropdown.classList.remove('show');

        // Fetch and show receipt, then trigger print
        fetch('/receipts/' + receiptId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    var receipt = data.receipt;

                    // Populate modal (same as showReceiptModal)
                    document.getElementById('modal-receipt-number').textContent = receipt.receipt_number;
                    document.getElementById('modal-receipt-date').textContent = receipt.created_at || receipt.created_date || '-';
                    document.getElementById('modal-payment-mode').textContent = receipt.payment_mode_display || '-';

                    var titleEl = document.getElementById('modal-receipt-title');
                    if (titleEl) {
                        var typeUpper = (receipt.transaction_type || '').toUpperCase();
                        if (typeUpper === 'CREDIT') {
                            titleEl.textContent = 'CREDIT RECEIPT';
                        } else if (typeUpper === 'DEBIT') {
                            titleEl.textContent = 'DEBIT RECEIPT';
                        } else {
                            titleEl.textContent = 'RECEIPT';
                        }
                    }

                    document.getElementById('modal-member-name').textContent = receipt.member_name || '-';
                    document.getElementById('modal-member-id').textContent = receipt.member_id || '-';
                    document.getElementById('modal-member-mobile').textContent = receipt.member_mobile || '-';
                    document.getElementById('modal-member-address').textContent = receipt.member_address || '-';
                    document.getElementById('modal-account-number').textContent = receipt.account_number || '-';
                    document.getElementById('modal-account-type').textContent = receipt.account_type_display || '-';
                    document.getElementById('modal-transaction-type').textContent = receipt.transaction_type_display || '-';
                    document.getElementById('modal-amount').textContent = '\u20B9 ' + formatCurrency(receipt.amount);
                    document.getElementById('modal-balance-after').textContent = '\u20B9 ' + formatCurrency(receipt.balance_after);

                    var refRow = document.getElementById('modal-reference-row');
                    var refEl = document.getElementById('modal-reference');
                    if (receipt.reference_number) {
                        refEl.textContent = receipt.reference_number;
                        refRow.style.display = '';
                    } else {
                        refRow.style.display = 'none';
                    }

                    var descSection = document.getElementById('modal-description-section');
                    var descEl = document.getElementById('modal-description');
                    if (receipt.description) {
                        descEl.textContent = receipt.description;
                        descSection.style.display = '';
                    } else {
                        descSection.style.display = 'none';
                    }

                    var remarksSection = document.getElementById('modal-remarks-section');
                    var remarksEl = document.getElementById('modal-remarks');
                    if (receipt.remarks) {
                        remarksEl.textContent = receipt.remarks;
                        remarksSection.style.display = '';
                    } else {
                        remarksSection.style.display = 'none';
                    }

                    document.getElementById('modal-created-by').textContent = receipt.created_by_name || '-';

                    receiptModal.classList.add('show');

                    // Wait for modal to render, then print
                    setTimeout(function () {
                        window.print();
                    }, 300);
                } else {
                    alert('Error loading receipt: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading receipt: ' + error);
            });
    }

    /**
     * Print the currently open receipt
     */
    function printCurrentReceipt() {
        window.print();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose public API
    window.ReceiptsModule = {
        showReceiptModal: showReceiptModal,
        closeReceiptModal: closeReceiptModal,
        showAddReceiptModal: showAddReceiptModal,
        closeAddReceiptModal: closeAddReceiptModal,
        addReceipt: addReceipt,
        toggleDropdown: toggleDropdown,
        printReceipt: printReceipt,
        printCurrentReceipt: printCurrentReceipt
    };

    // Also expose as globals for onclick handlers in HTML
    window.showReceiptModal = showReceiptModal;
    window.closeReceiptModal = closeReceiptModal;
    window.showAddReceiptModal = showAddReceiptModal;
    window.closeAddReceiptModal = closeAddReceiptModal;
    window.addReceipt = addReceipt;
    window.toggleDropdown = toggleDropdown;
    window.printReceipt = printReceipt;
    window.printCurrentReceipt = printCurrentReceipt;

})();
