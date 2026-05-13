/**
 * Members management module
 * Handles member CRUD operations, modals, and dropdowns
 */
(function () {
    'use strict';

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHTML(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // State
    var deleteUserId = null;
    var isAddingMember = false;
    var isUpdatingMember = false;
    var currentMemberId = null;
    var txnPage = 1;
    var txnHasMore = false;

    // DOM Elements (cached on init)
    var memberModal, addMemberModal, editMemberModal, confirmDialog, passwordDialog;

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHTML(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Initialize the members module
     */
    function init() {
        // Cache modal elements
        memberModal = document.getElementById('memberModal');
        addMemberModal = document.getElementById('addMemberModal');
        editMemberModal = document.getElementById('editMemberModal');
        confirmDialog = document.getElementById('confirmDialog');
        passwordDialog = document.getElementById('passwordDialog');

        // Set up event listeners
        setupEventListeners();
    }

    /**
     * Set up global event listeners
     */
    function setupEventListeners() {
        // Close modals on outside click
        window.addEventListener('click', function (event) {
            if (event.target === memberModal) closeMemberModal();
            if (event.target === addMemberModal) closeAddMemberModal();
            if (event.target === editMemberModal) closeEditMemberModal();

            // Close dropdowns when clicking outside
            if (!event.target.matches('.kebab-menu')) {
                document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
                    menu.classList.remove('show');
                });
            }
        });

        // Close modals on Escape key
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeMemberModal();
                closeAddMemberModal();
                closeEditMemberModal();
                closeConfirmDialog();
                closePasswordDialog();
            }
        });
    }

    /**
     * Format currency for display
     */
    function formatCurrency(value) {
        var num = parseFloat(value);
        if (isNaN(num)) return '-';
        return '\u20b9' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    /**
     * Set text content safely
     */
    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value || '-';
    }

    /**
     * Show member details modal
     */
    function showMemberModal(memberId) {
        currentMemberId = memberId;
        txnPage = 1;
        txnHasMore = false;

        fetch('/members/' + memberId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    var user = data.user;

                    // Avatar and header
                    setText('modal-avatar', user.username.charAt(0).toUpperCase());
                    setText('modal-username', user.username);
                    setText('modal-email', user.email);

                    // Status badge
                    var statusBadge = document.getElementById('modal-status-badge');
                    if (statusBadge) {
                        statusBadge.textContent = user.status || '-';
                        statusBadge.className = 'status-badge status-' + (user.status_raw || 'active');
                    }

                    // Core Identity
                    setText('modal-member-id', user.member_id);
                    setText('modal-full-name', user.full_name);
                    setText('modal-member-type', user.member_type);
                    setText('modal-status', user.status);
                    setText('modal-date-joining', user.date_of_joining);
                    setText('modal-role', user.role_display);
                    setText('modal-date-joined', user.date_joined);
                    setText('modal-last-login', user.last_login);

                    // Personal
                    setText('modal-dob', user.date_of_birth);
                    setText('modal-age', user.age ? user.age + ' years' : '');
                    setText('modal-gender', user.gender);
                    setText('modal-marital', user.marital_status);
                    setText('modal-occupation', user.occupation);
                    setText('modal-income', user.annual_income_bracket);
                    setText('modal-education', user.education_qualification);

                    // Contact
                    setText('modal-mobile-primary', user.mobile_primary);
                    setText('modal-mobile-alt', user.mobile_alternate);
                    setText('modal-contact-email', user.email);
                    setText('modal-comm-mode', user.preferred_comm_mode);
                    setText('modal-dnd', user.dnd_enabled ? 'Yes' : 'No');
                    setText('modal-current-address', user.current_address);
                    setText('modal-permanent-address', user.permanent_address);

                    // KYC
                    setText('modal-kyc-status', user.kyc_status);
                    setText('modal-kyc-date', user.kyc_verified_date);
                    setText('modal-aadhar', user.aadhar_number);
                    setText('modal-pan', user.pan_number);
                    setText('modal-voter-id', user.voter_id);
                    setText('modal-passport', user.passport_number);
                    setText('modal-dl', user.driving_license);
                    setText('modal-aml', user.aml_check_status);

                    // Nominee
                    setText('modal-nominee-name', user.nominee_name);
                    setText('modal-nominee-rel', user.nominee_relationship);
                    setText('modal-nominee-dob', user.nominee_dob);
                    setText('modal-nominee-contact', user.nominee_contact);
                    setText('modal-nominee-address', user.nominee_address);
                    setText('modal-alt-nominee-name', user.alt_nominee_name);
                    setText('modal-alt-nominee-rel', user.alt_nominee_relationship);

                    // Shares
                    setText('modal-share-capital', formatCurrency(user.share_capital_amount));
                    setText('modal-num-shares', user.number_of_shares || '0');
                    setText('modal-face-value', formatCurrency(user.face_value_per_share));
                    setText('modal-cert-number', user.share_certificate_number);
                    setText('modal-share-date', user.share_issue_date);
                    setText('modal-dividend', formatCurrency(user.dividend_payable_balance));
                    setText('modal-last-dividend', user.last_dividend_paid_date);

                    // Eligibility
                    setEligibility('modal-elig-accounts', user.eligible_for_accounts);
                    setEligibility('modal-elig-loans', user.eligible_for_loans);
                    setEligibility('modal-elig-dividend', user.eligible_for_dividend);
                    setEligibility('modal-elig-voting', user.eligible_for_voting);
                    setText('modal-risk', user.risk_category);

                    // Render accounts table
                    renderAccountsTab(user.accounts || []);

                    // Reset transactions tab
                    var txnList = document.getElementById('modal-transactions-list');
                    if (txnList) txnList.innerHTML = '<p class="empty-state-text">Click to load transactions</p>';
                    var txnFooter = document.getElementById('modal-transactions-footer');
                    if (txnFooter) txnFooter.style.display = 'none';

                    // Reset to first tab and show modal
                    switchTab('core');
                    memberModal.classList.add('show');
                } else {
                    alert('Error loading member data: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading member data: ' + error);
            });
    }

    /**
     * Set eligibility display
     */
    function setEligibility(id, value) {
        var el = document.getElementById(id);
        if (el) {
            el.textContent = value ? 'Yes' : 'No';
            el.className = 'info-value ' + (value ? 'elig-yes' : 'elig-no');
        }
    }

    /**
     * Render accounts tab table
     */
    function renderAccountsTab(accounts) {
        var container = document.getElementById('modal-accounts-list');
        if (!container) return;

        if (!accounts || accounts.length === 0) {
            container.innerHTML = '<p class="empty-state-text">No accounts found for this user</p>';
            return;
        }

        var html = '<table class="modal-table">';
        html += '<thead><tr>';
        html += '<th>Account Number</th>';
        html += '<th>Type</th>';
        html += '<th style="text-align: right;">Balance</th>';
        html += '<th style="text-align: center;">Actions</th>';
        html += '</tr></thead><tbody>';

        for (var i = 0; i < accounts.length; i++) {
            var a = accounts[i];
            var balanceClass = parseFloat(a.balance) > 0 ? 'amount-credit' : '';
            html += '<tr>';
            html += '<td><strong>' + escapeHTML(a.account_number) + '</strong></td>';
            html += '<td>' + escapeHTML(a.account_type_display) + '</td>';
            html += '<td style="text-align: right;" class="' + balanceClass + '">' + formatCurrency(a.balance) + '</td>';
            html += '<td style="text-align: center;"><button class="btn btn-sm btn-secondary" onclick="viewAccountDetails(' + a.id + ')">Details</button></td>';
            html += '</tr>';
        }

        html += '</tbody></table>';
        container.innerHTML = html;
    }

    /**
     * Load transactions for the current member
     */
    function loadTransactions(page) {
        if (!currentMemberId) return;

        var container = document.getElementById('modal-transactions-list');
        if (page === 1 && container) {
            container.innerHTML = '<p class="empty-state-text">Loading transactions...</p>';
        }

        fetch('/api/members/' + currentMemberId + '/transactions/?page=' + page)
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    txnHasMore = data.has_more;
                    txnPage = data.page;

                    if (data.transactions.length === 0 && page === 1) {
                        container.innerHTML = '<p class="empty-state-text">No transactions found</p>';
                        document.getElementById('modal-transactions-footer').style.display = 'none';
                        return;
                    }

                    var html = '';
                    if (page === 1) {
                        html = '<table class="modal-table" id="modal-txn-table">';
                        html += '<thead><tr>';
                        html += '<th>Receipt #</th>';
                        html += '<th>Date</th>';
                        html += '<th>Type</th>';
                        html += '<th>Account</th>';
                        html += '<th>Amount</th>';
                        html += '<th>Balance</th>';
                        html += '</tr></thead><tbody>';
                    }

                    for (var i = 0; i < data.transactions.length; i++) {
                        var t = data.transactions[i];
                        var isCredit = ['credit', 'interest', 'dividend', 'share_capital'].indexOf(t.transaction_type) !== -1;
                        var amountClass = isCredit ? 'amount-credit' : 'amount-debit';
                        var prefix = isCredit ? '+' : '-';

                        html += '<tr>';
                        html += '<td>' + escapeHTML(t.transaction_number) + '</td>';
                        html += '<td>' + escapeHTML(t.created_at) + '</td>';
                        html += '<td>' + escapeHTML(t.transaction_type_display) + '</td>';
                        html += '<td>' + escapeHTML(t.account_number) + '</td>';
                        html += '<td class="' + amountClass + '">' + prefix + formatCurrency(t.amount) + '</td>';
                        html += '<td>' + formatCurrency(t.balance_after) + '</td>';
                        html += '</tr>';
                    }

                    if (page === 1) {
                        html += '</tbody></table>';
                        container.innerHTML = html;
                    } else {
                        // Append rows to existing table
                        var tbody = document.querySelector('#modal-txn-table tbody');
                        if (tbody) {
                            var temp = document.createElement('tbody');
                            temp.innerHTML = html;
                            while (temp.firstChild) {
                                tbody.appendChild(temp.firstChild);
                            }
                        }
                    }

                    // Show/hide load more
                    var footer = document.getElementById('modal-transactions-footer');
                    if (footer) {
                        footer.style.display = txnHasMore ? 'flex' : 'none';
                    }

                    var info = document.getElementById('modal-txn-info');
                    if (info) {
                        info.textContent = 'Showing ' + Math.min(txnPage * 15, data.total) + ' of ' + data.total;
                    }
                }
            })
            .catch(function (error) {
                container.innerHTML = '<p class="empty-state-text">Error loading transactions</p>';
            });
    }

    /**
     * Load more transactions (next page)
     */
    function loadMoreTransactions() {
        if (txnHasMore) {
            loadTransactions(txnPage + 1);
        }
    }

    /**
     * Close member details modal
     */
    function closeMemberModal() {
        if (memberModal) memberModal.classList.remove('show');
        currentMemberId = null;
    }

    function editCurrentMember() {
        if (!currentMemberId) return;
        openEditMember(currentMemberId, true);
    }

    /**
     * Switch modal tab
     */
    function switchTab(tabName) {
        // Deactivate all tabs and content
        var tabs = document.querySelectorAll('#memberModal .modal-tab');
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].classList.remove('active');
        }
        var contents = document.querySelectorAll('#memberModal .modal-tab-content');
        for (var j = 0; j < contents.length; j++) {
            contents[j].classList.remove('active');
        }

        // Activate clicked tab
        var tabNames = ['core', 'personal', 'contact', 'kyc', 'nominee', 'shares', 'accounts', 'transactions'];
        var index = tabNames.indexOf(tabName);
        if (index !== -1 && tabs[index]) {
            tabs[index].classList.add('active');
        }

        // Activate tab content
        var tabElement = document.getElementById('tab-' + tabName);
        if (tabElement) tabElement.classList.add('active');

        // Load transactions on first click of transactions tab
        if (tabName === 'transactions' && currentMemberId) {
            var container = document.getElementById('modal-transactions-list');
            if (container && container.querySelector('.empty-state-text')) {
                txnPage = 1;
                loadTransactions(1);
            }
        }
    }

    /**
     * Show add member modal
     */
    function showAddMemberModal() {
        document.getElementById('addMemberForm').reset();
        document.getElementById('add-member-error').style.display = 'none';
        var successDiv = document.getElementById('add-member-success');
        if (successDiv) successDiv.style.display = 'none';
        document.getElementById('addMemberBtn').disabled = false;
        isAddingMember = false;
        addMemberModal.classList.add('show');
    }

    /**
     * Close add member modal
     */
    function closeAddMemberModal() {
        if (addMemberModal) addMemberModal.classList.remove('show');
    }

    /**
     * Add a new member
     */
    function addMember() {
        if (isAddingMember) return;

        var form = document.getElementById('addMemberForm');
        var formData = new FormData(form);
        var errorDiv = document.getElementById('add-member-error');
        var successDiv = document.getElementById('add-member-success');
        var btn = document.getElementById('addMemberBtn');

        errorDiv.style.display = 'none';
        if (successDiv) successDiv.style.display = 'none';

        isAddingMember = true;
        btn.disabled = true;
        btn.textContent = 'Adding...';

        fetch('/members/add/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
            },
            body: formData
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    if (successDiv) {
                        successDiv.innerHTML = '<strong>Member added successfully!</strong><br>Password: <strong>' + escapeHTML(data.password) + '</strong><br>Please save this password.';
                        successDiv.style.display = 'block';
                    }
                    setTimeout(function () { window.location.reload(); }, 3000);
                } else {
                    errorDiv.textContent = data.error || 'Error creating member';
                    errorDiv.style.display = 'block';
                    isAddingMember = false;
                    btn.disabled = false;
                    btn.textContent = 'Add Member';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isAddingMember = false;
                btn.disabled = false;
                btn.textContent = 'Add Member';
            });
    }

    /**
     * Toggle dropdown menu
     */
    function toggleDropdown(event, memberId) {
        event.stopPropagation();

        document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
            if (menu.id !== 'dropdown-' + memberId) {
                menu.classList.remove('show');
            }
        });

        document.getElementById('dropdown-' + memberId).classList.toggle('show');
    }

    /**
     * Open edit member modal
     */
    function openEditMember(memberId, closeDetailsModal) {
        fetch('/members/' + memberId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    if (closeDetailsModal) {
                        closeMemberModal();
                    }
                    document.getElementById('edit-member-id').value = memberId;
                    document.getElementById('edit-username').value = data.user.username;
                    document.getElementById('edit-email').value = data.user.email;
                    document.getElementById('edit-full-name').value = data.user.full_name || '';
                    document.getElementById('edit-mobile').value = data.user.mobile_primary || '';
                    document.getElementById('edit-role').value = data.user.role;
                    document.getElementById('edit-status').value = data.user.status_raw || 'active';
                    document.getElementById('edit-closure-reason').value = data.user.closure_reason || '';
                    document.getElementById('edit-member-error').style.display = 'none';

                    editMemberModal.classList.add('show');
                } else {
                    alert('Error loading member data: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading member data: ' + error);
            });
    }

    function editMember(event, memberId) {
        event.stopPropagation();
        var dropdown = document.getElementById('dropdown-' + memberId);
        if (dropdown) {
            dropdown.classList.remove('show');
        }
        openEditMember(memberId, false);
    }

    /**
     * Close edit member modal
     */
    function closeEditMemberModal() {
        if (editMemberModal) editMemberModal.classList.remove('show');
        var btn = document.getElementById('updateMemberBtn');
        if (btn) btn.disabled = false;
        isUpdatingMember = false;
    }

    /**
     * Update member
     */
    function updateMember() {
        if (isUpdatingMember) return;

        var form = document.getElementById('editMemberForm');
        var formData = new FormData(form);
        var memberId = document.getElementById('edit-member-id').value;
        var errorDiv = document.getElementById('edit-member-error');
        var btn = document.getElementById('updateMemberBtn');

        errorDiv.style.display = 'none';
        isUpdatingMember = true;
        btn.disabled = true;
        btn.textContent = 'Updating...';

        fetch('/members/' + memberId + '/edit/', {
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
                    errorDiv.textContent = data.error || 'Error updating member';
                    errorDiv.style.display = 'block';
                    isUpdatingMember = false;
                    btn.disabled = false;
                    btn.textContent = 'Update Member';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isUpdatingMember = false;
                btn.disabled = false;
                btn.textContent = 'Update Member';
            });
    }

    /**
     * Reset member password
     */
    function resetPassword(event, memberId) {
        event.stopPropagation();
        document.getElementById('dropdown-' + memberId).classList.remove('show');

        document.getElementById('password-message').textContent = 'Resetting password...';
        document.getElementById('password-result').style.display = 'none';
        passwordDialog.classList.add('show');

        fetch('/members/' + memberId + '/reset-password/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': window.CSRF_TOKEN,
                'Content-Type': 'application/json',
            },
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    document.getElementById('password-message').textContent = 'Password has been reset successfully!';
                    document.getElementById('new-password').textContent = data.password;
                    document.getElementById('password-result').style.display = 'block';
                } else {
                    document.getElementById('password-message').textContent = 'Error: ' + (data.error || 'Unknown error');
                }
            })
            .catch(function (error) {
                document.getElementById('password-message').textContent = 'Error: ' + error;
            });
    }

    /**
     * Close password dialog
     */
    function closePasswordDialog() {
        if (passwordDialog) passwordDialog.classList.remove('show');
    }

    /**
     * Show delete confirmation
     */
    function confirmDelete(event, memberId, username) {
        event.stopPropagation();
        document.getElementById('dropdown-' + memberId).classList.remove('show');

        deleteUserId = memberId;
        document.getElementById('delete-username').textContent = username;
        confirmDialog.classList.add('show');
    }

    /**
     * Close confirmation dialog
     */
    function closeConfirmDialog() {
        if (confirmDialog) confirmDialog.classList.remove('show');
        deleteUserId = null;
    }

    /**
     * Delete member
     */
    function deleteMember() {
        if (deleteUserId) {
            fetch('/members/' + deleteUserId + '/delete/', {
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
                        alert('Error deleting member: ' + (data.error || 'Unknown error'));
                        closeConfirmDialog();
                    }
                })
                .catch(function (error) {
                    alert('Error deleting member: ' + error);
                    closeConfirmDialog();
                });
        }
    }

    /**
     * View account details (redirect to accounts page or show modal)
     */
    function viewAccountDetails(accountId) {
        fetch('/accounts/' + accountId + '/get/')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!data.success) {
                    alert('Error: ' + (data.error || 'Could not load account'));
                    return;
                }
                var acc = data.account;
                var html = '<div style="padding: 1rem;">';
                html += '<h3 style="margin: 0 0 1rem; font-size: 1.1rem;">' + escapeHTML(acc.account_type_display) + ' - ' + escapeHTML(acc.account_number) + '</h3>';
                html += '<table style="width: 100%; font-size: 0.85rem; border-collapse: collapse;">';
                html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Member</td><td style="padding: 0.4rem 0; font-weight: 600;">' + escapeHTML(acc.user_name) + ' (' + escapeHTML(acc.member_id) + ')</td></tr>';
                html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Status</td><td style="padding: 0.4rem 0;">' + escapeHTML(acc.status_display) + '</td></tr>';
                html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Balance</td><td style="padding: 0.4rem 0; font-weight: 700; color: #047857;">₹' + formatINR(parseFloat(acc.balance)) + '</td></tr>';
                html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Interest Rate</td><td style="padding: 0.4rem 0;">' + acc.interest_rate + '%</td></tr>';
                if (acc.principal_amount && acc.principal_amount !== '0.00') {
                    html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Principal</td><td style="padding: 0.4rem 0;">₹' + formatINR(parseFloat(acc.principal_amount)) + '</td></tr>';
                }
                if (acc.opening_date) {
                    html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Opening Date</td><td style="padding: 0.4rem 0;">' + acc.opening_date + '</td></tr>';
                }
                if (acc.maturity_date) {
                    html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Maturity Date</td><td style="padding: 0.4rem 0;">' + acc.maturity_date + '</td></tr>';
                }
                if (acc.tenure_months) {
                    html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Tenure</td><td style="padding: 0.4rem 0;">' + acc.tenure_months + ' months</td></tr>';
                }
                if (acc.nominee_name) {
                    html += '<tr><td style="padding: 0.4rem 0; color: #6b7280;">Nominee</td><td style="padding: 0.4rem 0;">' + escapeHTML(acc.nominee_name) + '</td></tr>';
                }
                html += '</table>';
                html += '<div style="margin-top: 1rem; text-align: right;">';
                html += '<a href="/accounts/' + acc.id + '/details/" style="font-size: 0.85rem; color: #2563eb;">Open Full Details</a>';
                html += '</div></div>';

                // Show in a simple overlay
                var overlay = document.createElement('div');
                overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;';
                var modal = document.createElement('div');
                modal.style.cssText = 'background:white;border-radius:12px;max-width:450px;width:90%;max-height:80vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);';
                modal.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;padding:1rem 1rem 0;"><span style="font-weight:600;font-size:0.9rem;color:#6b7280;">Account Details</span><button onclick="this.closest(\'div[style*=fixed]\').remove()" style="border:none;background:none;font-size:1.2rem;cursor:pointer;color:#9ca3af;">&times;</button></div>' + html;
                overlay.appendChild(modal);
                overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
                document.body.appendChild(overlay);
            })
            .catch(function() {
                alert('Error loading account details');
            });
    }

    function formatINR(num) {
        return num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
    }

    function escapeHTML(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose public API
    window.MembersModule = {
        showMemberModal: showMemberModal,
        closeMemberModal: closeMemberModal,
        editCurrentMember: editCurrentMember,
        switchTab: switchTab,
        showAddMemberModal: showAddMemberModal,
        closeAddMemberModal: closeAddMemberModal,
        addMember: addMember,
        toggleDropdown: toggleDropdown,
        editMember: editMember,
        closeEditMemberModal: closeEditMemberModal,
        updateMember: updateMember,
        resetPassword: resetPassword,
        closePasswordDialog: closePasswordDialog,
        confirmDelete: confirmDelete,
        closeConfirmDialog: closeConfirmDialog,
        deleteMember: deleteMember,
        loadMoreTransactions: loadMoreTransactions,
        viewAccountDetails: viewAccountDetails
    };

    // Also expose as globals for onclick handlers in HTML
    window.showMemberModal = showMemberModal;
    window.closeMemberModal = closeMemberModal;
    window.editCurrentMember = editCurrentMember;
    window.switchTab = switchTab;
    window.showAddMemberModal = showAddMemberModal;
    window.closeAddMemberModal = closeAddMemberModal;
    window.addMember = addMember;
    window.toggleDropdown = toggleDropdown;
    window.editMember = editMember;
    window.closeEditMemberModal = closeEditMemberModal;
    window.updateMember = updateMember;
    window.resetPassword = resetPassword;
    window.closePasswordDialog = closePasswordDialog;
    window.confirmDelete = confirmDelete;
    window.closeConfirmDialog = closeConfirmDialog;
    window.deleteMember = deleteMember;
    window.loadMoreTransactions = loadMoreTransactions;
    window.viewAccountDetails = viewAccountDetails;

})();
