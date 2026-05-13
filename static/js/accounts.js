/**
 * Accounts management module
 * Handles account CRUD operations, modals, dropdowns, and member search
 */
(function () {
    'use strict';

    // State
    var deleteAccountId = null;
    var isAddingAccount = false;
    var isUpdatingAccount = false;
    var searchTimeout = null;
    var currentAccountId = null;
    var txnPage = 1;
    var txnHasMore = false;
    var txnLoaded = false;

    // DOM Elements (cached on init)
    var accountModal, addAccountModal, editAccountModal, confirmDialog;

    /**
     * Initialize the accounts module
     */
    function init() {
        // Cache modal elements
        accountModal = document.getElementById('accountModal');
        addAccountModal = document.getElementById('addAccountModal');
        editAccountModal = document.getElementById('editAccountModal');
        confirmDialog = document.getElementById('confirmDialog');

        // Set up event listeners
        setupEventListeners();
    }

    /**
     * Set up global event listeners
     */
    function setupEventListeners() {
        // Close modals on outside click
        window.addEventListener('click', function (event) {
            if (event.target === accountModal) closeAccountModal();
            if (event.target === addAccountModal) closeAddAccountModal();
            if (event.target === editAccountModal) closeEditAccountModal();

            // Close dropdowns when clicking outside
            if (!event.target.matches('.kebab-menu')) {
                document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
                    menu.classList.remove('show');
                });
            }

            // Close member search results when clicking outside
            var memberSelector = document.querySelector('.member-selector');
            if (memberSelector && !memberSelector.contains(event.target)) {
                var results = document.getElementById('add-member-results');
                if (results) results.style.display = 'none';
            }
        });

        // Close modals on Escape key
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeAccountModal();
                closeAddAccountModal();
                closeEditAccountModal();
                closeConfirmDialog();
            }
        });

        // Member search input with debounce
        var memberSearchInput = document.getElementById('add-member-search');
        if (memberSearchInput) {
            memberSearchInput.addEventListener('input', function () {
                var query = this.value.trim();
                if (searchTimeout) clearTimeout(searchTimeout);

                if (query.length < 2) {
                    var results = document.getElementById('add-member-results');
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
     * Format date string to locale format
     */
    function formatDate(dateStr) {
        if (!dateStr) return '-';
        var d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('en-IN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    /**
     * Safely set text content of an element by ID
     */
    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value || '-';
    }

    /**
     * Show account details modal
     */
    function showAccountModal(accountId) {
        currentAccountId = accountId;
        txnPage = 1;
        txnHasMore = false;
        txnLoaded = false;

        fetch('/accounts/' + accountId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    var account = data.account;

                    // Type icon
                    var typeIconMap = {
                        'fd': 'FD',
                        'cd': 'CD',
                        'rd': 'RD',
                        'od': 'OD',
                        'share': 'SH',
                        'sukanya': 'SY',
                        'suputra': 'SP'
                    };
                    var iconEl = document.getElementById('modal-type-icon');
                    if (iconEl) {
                        iconEl.textContent = typeIconMap[account.account_type] || 'A';
                        iconEl.className = 'account-type-icon type-' + account.account_type;
                    }

                    // Header info
                    setText('modal-account-number', account.account_number);
                    setText('modal-account-type', account.account_type_display);

                    // Status badge
                    var statusBadge = document.getElementById('modal-status-badge');
                    if (statusBadge) {
                        statusBadge.textContent = account.status_display;
                        statusBadge.className = 'status-badge status-' + account.status;
                    }

                    // Balance
                    setText('modal-balance', formatCurrency(account.balance));

                    // Details grid
                    setText('modal-member-name', account.user_name);
                    setText('modal-member-id', account.member_id);
                    setText('modal-interest-rate', account.interest_rate ? account.interest_rate + '%' : '-');
                    setText('modal-principal', account.principal_amount ? formatCurrency(account.principal_amount) : '-');
                    setText('modal-opening-date', formatDate(account.opening_date));
                    setText('modal-maturity-date', formatDate(account.maturity_date));
                    setText('modal-tenure', account.tenure_months ? account.tenure_months + ' months' : '-');

                    // Nominee
                    var nominee = '-';
                    if (account.nominee_name) {
                        nominee = account.nominee_name;
                        if (account.nominee_relationship) {
                            nominee += ' (' + account.nominee_relationship + ')';
                        }
                    }
                    setText('modal-nominee', nominee);

                    // Remarks
                    var remarksSection = document.getElementById('remarks-section');
                    if (account.remarks) {
                        setText('modal-remarks', account.remarks);
                        if (remarksSection) remarksSection.style.display = 'block';
                    } else {
                        if (remarksSection) remarksSection.style.display = 'none';
                    }

                    // Reset to details tab
                    switchAccountTab('details');

                    // Reset statement tab
                    var tbody = document.getElementById('transactions-tbody');
                    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Click to load transactions</td></tr>';
                    var loadMore = document.getElementById('transactions-load-more');
                    if (loadMore) loadMore.style.display = 'none';
                    var summary = document.getElementById('transactions-summary');
                    if (summary) summary.textContent = '';

                    accountModal.classList.add('show');
                } else {
                    alert('Error loading account data: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading account data: ' + error);
            });
    }

    /**
     * Switch account modal tab
     */
    function switchAccountTab(tabName) {
        // Update tab buttons
        var tabs = document.querySelectorAll('#accountModal .modal-tab');
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].classList.remove('active');
            if (tabs[i].textContent.toLowerCase().indexOf(tabName === 'details' ? 'details' : 'statement') !== -1) {
                tabs[i].classList.add('active');
            }
        }

        // Update tab content
        var contents = document.querySelectorAll('#accountModal .modal-tab-content');
        for (var j = 0; j < contents.length; j++) {
            contents[j].classList.remove('active');
        }
        var activeTab = document.getElementById('tab-' + tabName);
        if (activeTab) activeTab.classList.add('active');

        // Load transactions when switching to statement tab for the first time
        if (tabName === 'statement' && !txnLoaded) {
            loadAccountTransactions(false);
        }
    }

    /**
     * Load account transactions
     */
    function loadAccountTransactions(append) {
        if (!currentAccountId) return;

        var tbody = document.getElementById('transactions-tbody');
        if (!tbody) return;

        if (!append) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Loading transactions...</td></tr>';
        }

        fetch('/accounts/' + currentAccountId + '/transactions/?page=' + txnPage)
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    txnLoaded = true;
                    if (!append) {
                        tbody.innerHTML = '';
                    }

                    if (data.transactions.length === 0 && !append) {
                        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No transactions found</td></tr>';
                    } else {
                        for (var i = 0; i < data.transactions.length; i++) {
                            var txn = data.transactions[i];
                            var row = document.createElement('tr');
                            var typeClass = txn.type_raw === 'credit' || txn.type_raw === 'interest' || txn.type_raw === 'dividend' ? 'credit' : 'debit';
                            row.innerHTML = '<td><span class="account-number">' + escapeHTML(txn.transaction_number) + '</span></td>' +
                                '<td>' + escapeHTML(txn.date) + '</td>' +
                                '<td><span class="txn-type-badge txn-' + escapeHTML(typeClass) + '">' + escapeHTML(txn.type) + '</span></td>' +
                                '<td>' + escapeHTML(txn.description) + '</td>' +
                                '<td style="text-align: right; font-family: monospace;">' + formatCurrency(txn.amount) + '</td>' +
                                '<td style="text-align: right; font-family: monospace;">' + (txn.balance_after !== '-' ? formatCurrency(txn.balance_after) : '-') + '</td>';
                            tbody.appendChild(row);
                        }
                    }

                    txnHasMore = data.has_more;
                    var loadMoreBtn = document.getElementById('transactions-load-more');
                    if (loadMoreBtn) {
                        loadMoreBtn.style.display = data.has_more ? 'block' : 'none';
                    }

                    var summary = document.getElementById('transactions-summary');
                    if (summary) {
                        summary.textContent = 'Showing ' + tbody.children.length + ' of ' + data.total + ' transactions';
                    }
                }
            })
            .catch(function (error) {
                console.error('Error loading transactions:', error);
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Error loading transactions: ' + escapeHTML(error.message) + '</td></tr>';
            });
    }

    /**
     * Load more transactions (next page)
     */
    function loadMoreTransactions() {
        if (!txnHasMore) return;
        txnPage++;
        loadAccountTransactions(true);
    }

    /**
     * Close account view modal
     */
    function closeAccountModal() {
        if (accountModal) accountModal.classList.remove('show');
        currentAccountId = null;
    }

    /**
     * Show add account modal
     */
    function showAddAccountModal() {
        var form = document.getElementById('addAccountForm');
        if (form) form.reset();

        var errorDiv = document.getElementById('add-account-error');
        if (errorDiv) errorDiv.style.display = 'none';

        var memberSearch = document.getElementById('add-member-search');
        if (memberSearch) memberSearch.value = '';

        var memberId = document.getElementById('add-member-id');
        if (memberId) memberId.value = '';

        var results = document.getElementById('add-member-results');
        if (results) results.style.display = 'none';

        var btn = document.getElementById('addAccountBtn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Add Account';
        }

        isAddingAccount = false;
        addAccountModal.classList.add('show');
    }

    /**
     * Close add account modal
     */
    function closeAddAccountModal() {
        if (addAccountModal) addAccountModal.classList.remove('show');
    }

    /**
     * Add a new account
     */
    function addAccount() {
        if (isAddingAccount) return;

        var form = document.getElementById('addAccountForm');
        var formData = new FormData(form);
        var errorDiv = document.getElementById('add-account-error');
        var btn = document.getElementById('addAccountBtn');

        // Validate member selected
        if (!formData.get('user_id')) {
            errorDiv.textContent = 'Please select a member';
            errorDiv.style.display = 'block';
            return;
        }

        errorDiv.style.display = 'none';
        isAddingAccount = true;
        btn.disabled = true;
        btn.textContent = 'Adding...';

        fetch('/accounts/add/', {
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
                    errorDiv.textContent = data.error || 'Error creating account';
                    errorDiv.style.display = 'block';
                    isAddingAccount = false;
                    btn.disabled = false;
                    btn.textContent = 'Add Account';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isAddingAccount = false;
                btn.disabled = false;
                btn.textContent = 'Add Account';
            });
    }

    /**
     * Show edit account modal
     */
    function showEditAccountModal(event, accountId) {
        event.stopPropagation();
        var dropdown = document.getElementById('dropdown-' + accountId);
        if (dropdown) dropdown.classList.remove('show');

        fetch('/accounts/' + accountId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    var account = data.account;

                    document.getElementById('edit-account-id').value = account.id;
                    document.getElementById('edit-account-number').value = account.account_number;
                    document.getElementById('edit-account-type').value = account.account_type;
                    document.getElementById('edit-status').value = account.status;
                    document.getElementById('edit-balance').value = account.balance;
                    document.getElementById('edit-interest-rate').value = account.interest_rate;
                    document.getElementById('edit-principal').value = account.principal_amount;
                    document.getElementById('edit-opening-date').value = account.opening_date;
                    document.getElementById('edit-maturity-date').value = account.maturity_date;
                    document.getElementById('edit-tenure').value = account.tenure_months || '';
                    document.getElementById('edit-nominee-name').value = account.nominee_name || '';
                    document.getElementById('edit-nominee-relationship').value = account.nominee_relationship || '';
                    document.getElementById('edit-remarks').value = account.remarks || '';

                    var errorDiv = document.getElementById('edit-account-error');
                    if (errorDiv) errorDiv.style.display = 'none';

                    var btn = document.getElementById('updateAccountBtn');
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = 'Update Account';
                    }

                    isUpdatingAccount = false;
                    editAccountModal.classList.add('show');
                } else {
                    alert('Error loading account data: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading account data: ' + error);
            });
    }

    /**
     * Close edit account modal
     */
    function closeEditAccountModal() {
        if (editAccountModal) editAccountModal.classList.remove('show');
        var btn = document.getElementById('updateAccountBtn');
        if (btn) btn.disabled = false;
        isUpdatingAccount = false;
    }

    /**
     * Update account
     */
    function updateAccount() {
        if (isUpdatingAccount) return;

        var form = document.getElementById('editAccountForm');
        var formData = new FormData(form);
        var accountId = document.getElementById('edit-account-id').value;
        var errorDiv = document.getElementById('edit-account-error');
        var btn = document.getElementById('updateAccountBtn');

        errorDiv.style.display = 'none';
        isUpdatingAccount = true;
        btn.disabled = true;
        btn.textContent = 'Updating...';

        fetch('/accounts/' + accountId + '/edit/', {
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
                    errorDiv.textContent = data.error || 'Error updating account';
                    errorDiv.style.display = 'block';
                    isUpdatingAccount = false;
                    btn.disabled = false;
                    btn.textContent = 'Update Account';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isUpdatingAccount = false;
                btn.disabled = false;
                btn.textContent = 'Update Account';
            });
    }

    /**
     * Show delete confirmation
     */
    function confirmDeleteAccount(event, accountId, accountNumber) {
        event.stopPropagation();
        var dropdown = document.getElementById('dropdown-' + accountId);
        if (dropdown) dropdown.classList.remove('show');

        deleteAccountId = accountId;
        document.getElementById('delete-account-number').textContent = accountNumber;
        confirmDialog.classList.add('show');
    }

    /**
     * Close confirmation dialog
     */
    function closeConfirmDialog() {
        if (confirmDialog) confirmDialog.classList.remove('show');
        deleteAccountId = null;
    }

    /**
     * Delete account
     */
    function deleteAccount() {
        if (!deleteAccountId) return;

        fetch('/accounts/' + deleteAccountId + '/delete/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': window.CSRF_TOKEN,
                'Content-Type': 'application/json',
            },
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    window.location.reload();
                } else {
                    alert('Error deleting account: ' + (data.error || 'Unknown error'));
                    closeConfirmDialog();
                }
            })
            .catch(function (error) {
                alert('Error deleting account: ' + error);
                closeConfirmDialog();
            });
    }

    /**
     * Toggle dropdown menu
     */
    function toggleDropdown(event, accountId) {
        event.stopPropagation();

        document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
            if (menu.id !== 'dropdown-' + accountId) {
                menu.classList.remove('show');
            }
        });

        document.getElementById('dropdown-' + accountId).classList.toggle('show');
    }

    /**
     * Search members for autocomplete
     */
    function searchMembers(query) {
        fetch('/api/members/search/?q=' + encodeURIComponent(query))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                var resultsDiv = document.getElementById('add-member-results');
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

                            document.getElementById('add-member-id').value = memberId;
                            document.getElementById('add-member-search').value = memberName;
                            resultsDiv.style.display = 'none';
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

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose public API
    window.AccountsModule = {
        showAccountModal: showAccountModal,
        closeAccountModal: closeAccountModal,
        switchAccountTab: switchAccountTab,
        loadMoreTransactions: loadMoreTransactions,
        showAddAccountModal: showAddAccountModal,
        closeAddAccountModal: closeAddAccountModal,
        addAccount: addAccount,
        showEditAccountModal: showEditAccountModal,
        closeEditAccountModal: closeEditAccountModal,
        updateAccount: updateAccount,
        confirmDeleteAccount: confirmDeleteAccount,
        closeConfirmDialog: closeConfirmDialog,
        deleteAccount: deleteAccount,
        toggleDropdown: toggleDropdown
    };

    // Also expose as globals for onclick handlers in HTML
    window.showAccountModal = showAccountModal;
    window.closeAccountModal = closeAccountModal;
    window.switchAccountTab = switchAccountTab;
    window.loadMoreTransactions = loadMoreTransactions;
    window.showAddAccountModal = showAddAccountModal;
    window.closeAddAccountModal = closeAddAccountModal;
    window.addAccount = addAccount;
    window.showEditAccountModal = showEditAccountModal;
    window.closeEditAccountModal = closeEditAccountModal;
    window.updateAccount = updateAccount;
    window.confirmDeleteAccount = confirmDeleteAccount;
    window.closeConfirmDialog = closeConfirmDialog;
    window.deleteAccount = deleteAccount;
    window.toggleDropdown = toggleDropdown;

})();
