/**
 * Loans management module
 * Handles loan viewing, creation, approval, EMI recording, and repayment schedule
 */
(function () {
    'use strict';

    // State
    var currentLoanId = null;
    var currentLoanStatus = null;
    var currentLoanListKind = 'account';
    var approveLoanId = null;
    var isAddingLoan = false;
    var isApproving = false;
    var isRecordingEmi = false;
    var searchTimeout = null;

    // DOM Elements (cached on init)
    var loanModal, addLoanModal, approveDialog, emiDialog;

    /**
     * Initialize the loans module
     */
    function init() {
        loanModal = document.getElementById('loanModal');
        addLoanModal = document.getElementById('addLoanModal');
        approveDialog = document.getElementById('approveDialog');
        emiDialog = document.getElementById('emiDialog');

        setupEventListeners();
    }

    /**
     * Set up global event listeners
     */
    function setupEventListeners() {
        // Close modals on outside click
        window.addEventListener('click', function (event) {
            if (event.target === loanModal) closeLoanModal();
            if (event.target === addLoanModal) closeAddLoanModal();
            if (event.target === approveDialog) closeApproveDialog();
            if (event.target === emiDialog) closeEmiDialog();

            // Close dropdowns when clicking outside
            if (!event.target.matches('.kebab-menu')) {
                document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
                    menu.classList.remove('show');
                });
            }

            // Close member search results when clicking outside
            var memberSelector = document.querySelector('.member-selector');
            if (memberSelector && !memberSelector.contains(event.target)) {
                var results = document.getElementById('loan-member-results');
                if (results) results.style.display = 'none';
            }
        });

        // Close modals on Escape key
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeLoanModal();
                closeAddLoanModal();
                closeApproveDialog();
                closeEmiDialog();
            }
        });

        // Member search input with debounce
        var memberSearchInput = document.getElementById('loan-member-search');
        if (memberSearchInput) {
            memberSearchInput.addEventListener('input', function () {
                var query = this.value.trim();
                if (searchTimeout) clearTimeout(searchTimeout);

                if (query.length < 2) {
                    var results = document.getElementById('loan-member-results');
                    if (results) results.style.display = 'none';
                    return;
                }

                searchTimeout = setTimeout(function () {
                    searchMembers(query);
                }, 300);
            });
        }

        var loanTypeInput = document.getElementById('loan-type-input');
        if (loanTypeInput) {
            loanTypeInput.addEventListener('change', applyDefaultInterestRate);
        }
    }

    function applyDefaultInterestRate() {
        var loanTypeInput = document.getElementById('loan-type-input');
        var rateInput = document.getElementById('loan-interest-rate-input');
        if (!loanTypeInput || !rateInput) return;
        var selected = loanTypeInput.options[loanTypeInput.selectedIndex];
        if (!selected) return;
        var defaultRate = selected.getAttribute('data-default-rate');
        if (defaultRate && defaultRate !== '') {
            rateInput.value = defaultRate;
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
     * Toggle dropdown menu
     */
    function toggleDropdown(event, listKind, loanId) {
        event.stopPropagation();
        listKind = listKind || 'account';
        var menuId = 'dropdown-' + listKind + '-' + loanId;

        document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
            if (menu.id !== menuId) {
                menu.classList.remove('show');
            }
        });

        var menu = document.getElementById(menuId);
        if (menu) menu.classList.toggle('show');
    }

    /**
     * Search members for autocomplete
     */
    function searchMembers(query) {
        fetch('/api/members/search/?q=' + encodeURIComponent(query))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                var resultsDiv = document.getElementById('loan-member-results');
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

                    resultsDiv.querySelectorAll('.member-selector-item').forEach(function (item) {
                        item.addEventListener('click', function () {
                            var memberId = this.getAttribute('data-id');
                            var memberName = this.getAttribute('data-name');

                            document.getElementById('loan-member-id').value = memberId;
                            document.getElementById('loan-member-search').value = memberName;
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

    // ========================================
    // Loan View Modal
    // ========================================

    /**
     * Show loan details modal
     */
    function showLoanModal(loanId, listKind) {
        listKind = listKind || 'account';
        var url = '/loans/' + loanId + '/get/?kind=' + encodeURIComponent(listKind);
        fetch(url)
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    currentLoanListKind = data.loan.list_kind || listKind;
                    populateLoanModal(data.loan);
                    currentLoanId = loanId;
                    currentLoanStatus = data.loan.status;

                    // Show/hide approve button (applications only)
                    var approveBtn = document.getElementById('modal-approve-btn');
                    if (approveBtn) {
                        var showApprove = data.loan.list_kind === 'application' && data.loan.status === 'pending';
                        approveBtn.style.display = showApprove ? 'inline-block' : 'none';
                    }

                    // Reset to details tab
                    switchLoanTab('details');
                    loanModal.classList.add('show');
                } else {
                    alert('Error loading loan data: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading loan data: ' + error);
            });
    }

    /**
     * Populate loan modal with data
     */
    function populateLoanModal(loan) {
        // Header
        document.getElementById('modal-loan-number').textContent = loan.loan_number;

        // Details tab
        document.getElementById('detail-loan-number').innerHTML = '<span class="loan-number">' + escapeHTML(loan.loan_number) + '</span>';
        document.getElementById('detail-status').innerHTML = '<span class="status-badge status-' + escapeHTML(loan.status) + '">' + escapeHTML(loan.status_display) + '</span>';
        document.getElementById('detail-member').textContent = loan.member_name || '-';
        document.getElementById('detail-member-id').textContent = loan.member_id || '-';
        document.getElementById('detail-loan-type').innerHTML = '<span class="loan-type-badge type-' + escapeHTML(loan.loan_type) + '">' + escapeHTML(loan.loan_type_display) + '</span>';
        document.getElementById('detail-interest-type').textContent = loan.interest_type_display || '-';
        document.getElementById('detail-application-date').textContent = loan.application_date || '-';
        document.getElementById('detail-approval-date').textContent = loan.approval_date || '-';
        document.getElementById('detail-disbursement-date').textContent = loan.disbursement_date || '-';
        document.getElementById('detail-disbursement-account').textContent = loan.disbursement_account_number || '-';
        document.getElementById('detail-approved-by').textContent = loan.approved_by_name || '-';
        document.getElementById('detail-created-by').textContent = loan.created_by_name || '-';

        // Purpose
        var purposeSection = document.getElementById('detail-purpose-section');
        if (loan.purpose) {
            document.getElementById('detail-purpose').textContent = loan.purpose;
            purposeSection.style.display = 'block';
        } else {
            purposeSection.style.display = 'none';
        }

        // Remarks
        var remarksSection = document.getElementById('detail-remarks-section');
        if (loan.remarks) {
            document.getElementById('detail-remarks').textContent = loan.remarks;
            remarksSection.style.display = 'block';
        } else {
            remarksSection.style.display = 'none';
        }

        // Financials tab
        document.getElementById('fin-principal').textContent = formatCurrency(loan.principal_amount);
        document.getElementById('fin-total-payable').textContent = formatCurrency(loan.total_payable);
        document.getElementById('fin-total-paid').textContent = formatCurrency(loan.total_paid);
        document.getElementById('fin-outstanding').textContent = formatCurrency(loan.outstanding_balance);

        // Progress bar
        var progress = loan.completion_percentage || 0;
        document.getElementById('fin-progress-text').textContent = progress + '%';
        document.getElementById('fin-progress-fill').style.width = progress + '%';

        // Financial details
        document.getElementById('fin-interest-rate').textContent = loan.interest_rate ? loan.interest_rate + '% p.a.' : '-';
        document.getElementById('fin-interest-type').textContent = loan.interest_type_display || '-';
        document.getElementById('fin-tenure').textContent = loan.tenure_months ? loan.tenure_months + ' months' : '-';
        document.getElementById('fin-emi').textContent = formatCurrency(loan.emi_amount);
        document.getElementById('fin-emis-paid').textContent = (loan.emis_paid || 0) + ' / ' + (loan.total_emis || 0);
        document.getElementById('fin-emis-overdue').textContent = loan.emis_overdue || '0';
        document.getElementById('fin-first-emi').textContent = loan.first_emi_date || '-';
        document.getElementById('fin-last-emi').textContent = loan.last_emi_date || '-';
        document.getElementById('fin-overdue-amount').textContent = formatCurrency(loan.overdue_amount);
        document.getElementById('fin-closure-date').textContent = loan.closure_date || '-';

        // Guarantor tab
        document.getElementById('guar-name').textContent = loan.guarantor_name || '-';
        document.getElementById('guar-member-id').textContent = loan.guarantor_member_id || '-';
        document.getElementById('guar-relationship').textContent = loan.guarantor_relationship || '-';
        document.getElementById('guar-contact').textContent = loan.guarantor_contact || '-';

        // Collateral tab
        document.getElementById('coll-type').textContent = loan.collateral_type || '-';
        document.getElementById('coll-value').textContent = loan.collateral_value ? formatCurrency(loan.collateral_value) : '-';

        var collDescSection = document.getElementById('coll-desc-section');
        if (loan.collateral_description) {
            document.getElementById('coll-description').textContent = loan.collateral_description;
            collDescSection.style.display = 'block';
        } else {
            collDescSection.style.display = 'none';
        }

        // Repayment schedule
        renderRepaymentSchedule(loan.repayments, loan.status, loan.list_kind || 'account');
    }

    /**
     * Render the repayment schedule table
     */
    function renderRepaymentSchedule(repayments, loanStatus, listKind) {
        listKind = listKind || 'account';
        var tbody = document.getElementById('repayment-tbody');
        var noRepayments = document.getElementById('no-repayments');
        var table = document.getElementById('repayment-table');

        if (!repayments || repayments.length === 0) {
            tbody.innerHTML = '';
            table.style.display = 'none';
            noRepayments.style.display = 'block';
            return;
        }

        table.style.display = '';
        noRepayments.style.display = 'none';

        var html = '';
        repayments.forEach(function (r) {
            var rowClass = 'repayment-' + escapeHTML(r.payment_status);
            var statusClass = 'ps-' + escapeHTML(r.payment_status);

            html += '<tr class="' + rowClass + '">';
            html += '<td>' + escapeHTML(String(r.installment_number)) + '</td>';
            html += '<td>' + escapeHTML(r.due_date) + '</td>';
            html += '<td style="text-align: right;">' + formatCurrency(r.amount_due) + '</td>';
            html += '<td style="text-align: right;">' + formatCurrency(r.principal_component) + '</td>';
            html += '<td style="text-align: right;">' + formatCurrency(r.interest_component) + '</td>';
            html += '<td>' + escapeHTML(r.paid_date || '-') + '</td>';
            html += '<td style="text-align: right;">' + (r.amount_paid && parseFloat(r.amount_paid) > 0 ? formatCurrency(r.amount_paid) : '-') + '</td>';
            html += '<td><span class="payment-status ' + statusClass + '">' + escapeHTML(r.payment_status_display) + '</span></td>';
            html += '<td>';
            if ((r.payment_status === 'upcoming' || r.payment_status === 'overdue' || r.payment_status === 'partial') && loanStatus === 'active' && listKind === 'account') {
                html += '<button class="emi-pay-btn" onclick="showRecordEmiDialog(' + parseInt(currentLoanId, 10) + ', ' + parseInt(r.installment_number, 10) + ', \'' + escapeHTML(r.amount_due) + '\')">Pay</button>';
            }
            html += '</td>';
            html += '</tr>';
        });

        tbody.innerHTML = html;
    }

    /**
     * Switch between loan modal tabs
     */
    function switchLoanTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('#loanModal .modal-tab').forEach(function (tab) {
            tab.classList.remove('active');
        });
        // Find the clicked tab by matching text content
        var tabMap = { 'details': 0, 'financials': 1, 'guarantor': 2, 'schedule': 3 };
        var tabs = document.querySelectorAll('#loanModal .modal-tab');
        if (tabs[tabMap[tabName]]) {
            tabs[tabMap[tabName]].classList.add('active');
        }

        // Update tab content
        document.querySelectorAll('#loanModal .modal-tab-content').forEach(function (content) {
            content.classList.remove('active');
        });
        var tabContent = document.getElementById('tab-' + tabName);
        if (tabContent) tabContent.classList.add('active');
    }

    /**
     * Close loan view modal
     */
    function closeLoanModal() {
        if (loanModal) loanModal.classList.remove('show');
        currentLoanId = null;
        currentLoanStatus = null;
        currentLoanListKind = 'account';
    }

    // ========================================
    // Add Loan
    // ========================================

    /**
     * Show add loan modal
     */
    function showAddLoanModal() {
        var form = document.getElementById('addLoanForm');
        if (form) form.reset();

        var errorDiv = document.getElementById('add-loan-error');
        if (errorDiv) errorDiv.style.display = 'none';

        var memberSearch = document.getElementById('loan-member-search');
        if (memberSearch) memberSearch.value = '';

        var memberId = document.getElementById('loan-member-id');
        if (memberId) memberId.value = '';

        var results = document.getElementById('loan-member-results');
        if (results) results.style.display = 'none';

        var btn = document.getElementById('addLoanBtn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Add Loan';
        }

        isAddingLoan = false;
        applyDefaultInterestRate();
        addLoanModal.classList.add('show');
    }

    /**
     * Close add loan modal
     */
    function closeAddLoanModal() {
        if (addLoanModal) addLoanModal.classList.remove('show');
    }

    /**
     * Add a new loan
     */
    function addLoan() {
        if (isAddingLoan) return;

        var form = document.getElementById('addLoanForm');
        var formData = new FormData(form);
        var errorDiv = document.getElementById('add-loan-error');
        var btn = document.getElementById('addLoanBtn');

        if (!formData.get('user_id')) {
            errorDiv.textContent = 'Please select a member';
            errorDiv.style.display = 'block';
            return;
        }

        errorDiv.style.display = 'none';
        isAddingLoan = true;
        btn.disabled = true;
        btn.textContent = 'Adding...';

        fetch('/loans/add/', {
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
                    errorDiv.textContent = data.error || 'Error creating loan';
                    errorDiv.style.display = 'block';
                    isAddingLoan = false;
                    btn.disabled = false;
                    btn.textContent = 'Add Loan';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isAddingLoan = false;
                btn.disabled = false;
                btn.textContent = 'Add Loan';
            });
    }

    // ========================================
    // Approve Loan
    // ========================================

    /**
     * Show approve dialog from kebab menu
     */
    function showApproveDialog(event, loanId) {
        event.stopPropagation();
        document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
            menu.classList.remove('show');
        });

        approveLoanId = loanId;
        openApproveDialog();
    }

    /**
     * Show approve dialog from within the loan modal
     */
    function showApproveDialogFromModal() {
        if (!currentLoanId) return;
        approveLoanId = currentLoanId;
        openApproveDialog();
    }

    /**
     * Open the approve dialog (shared logic)
     */
    function openApproveDialog() {
        var loanNumberEl = document.getElementById('approve-loan-number');
        var modalLoanNumber = document.getElementById('modal-loan-number');
        if (loanNumberEl && modalLoanNumber) {
            loanNumberEl.textContent = modalLoanNumber.textContent;
        }

        // Set default disbursement date to today
        var dateInput = document.getElementById('approve-disbursement-date');
        if (dateInput) {
            var today = new Date();
            var yyyy = today.getFullYear();
            var mm = String(today.getMonth() + 1).padStart(2, '0');
            var dd = String(today.getDate()).padStart(2, '0');
            dateInput.value = yyyy + '-' + mm + '-' + dd;
        }

        var errorDiv = document.getElementById('approve-error');
        if (errorDiv) errorDiv.style.display = 'none';

        var btn = document.getElementById('approveBtn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Approve';
        }

        isApproving = false;
        approveDialog.classList.add('show');
    }

    /**
     * Close approve dialog
     */
    function closeApproveDialog() {
        if (approveDialog) approveDialog.classList.remove('show');
        approveLoanId = null;
    }

    /**
     * Submit loan approval
     */
    function approveLoan() {
        if (isApproving || !approveLoanId) return;

        var form = document.getElementById('approveForm');
        var formData = new FormData(form);
        var errorDiv = document.getElementById('approve-error');
        var btn = document.getElementById('approveBtn');

        var disbursementDate = document.getElementById('approve-disbursement-date').value;
        if (!disbursementDate) {
            errorDiv.textContent = 'Please enter a disbursement date';
            errorDiv.style.display = 'block';
            return;
        }

        errorDiv.style.display = 'none';
        isApproving = true;
        btn.disabled = true;
        btn.textContent = 'Approving...';

        fetch('/loans/' + approveLoanId + '/approve/', {
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
                    errorDiv.textContent = data.error || 'Error approving loan';
                    errorDiv.style.display = 'block';
                    isApproving = false;
                    btn.disabled = false;
                    btn.textContent = 'Approve';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isApproving = false;
                btn.disabled = false;
                btn.textContent = 'Approve';
            });
    }

    // ========================================
    // Record EMI Payment
    // ========================================

    /**
     * Show record EMI from the kebab menu (opens loan modal first to get data)
     */
    function showRecordEmiFromMenu(event, loanId, listKind) {
        event.stopPropagation();
        listKind = listKind || 'account';
        document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
            menu.classList.remove('show');
        });

        // Open loan modal to the schedule tab
        fetch('/loans/' + loanId + '/get/?kind=' + encodeURIComponent(listKind))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    currentLoanListKind = data.loan.list_kind || listKind;
                    populateLoanModal(data.loan);
                    currentLoanId = loanId;
                    currentLoanStatus = data.loan.status;

                    var approveBtn = document.getElementById('modal-approve-btn');
                    if (approveBtn) approveBtn.style.display = 'none';

                    switchLoanTab('schedule');
                    loanModal.classList.add('show');
                } else {
                    alert('Error loading loan data: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) {
                alert('Error loading loan data: ' + error);
            });
    }

    /**
     * Show the record EMI payment dialog
     */
    function showRecordEmiDialog(loanId, installmentNumber, amountDue) {
        document.getElementById('emi-loan-id').value = loanId;
        document.getElementById('emi-installment').value = installmentNumber;
        document.getElementById('emi-amount-due').value = formatCurrency(amountDue);
        document.getElementById('emi-amount-paid').value = parseFloat(amountDue).toFixed(2);

        var errorDiv = document.getElementById('emi-error');
        if (errorDiv) errorDiv.style.display = 'none';

        var btn = document.getElementById('emiBtn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Record Payment';
        }

        isRecordingEmi = false;
        emiDialog.classList.add('show');
    }

    /**
     * Close EMI dialog
     */
    function closeEmiDialog() {
        if (emiDialog) emiDialog.classList.remove('show');
    }

    /**
     * Submit EMI payment
     */
    function recordEmiPayment() {
        if (isRecordingEmi) return;

        var form = document.getElementById('emiForm');
        var formData = new FormData(form);
        var loanId = document.getElementById('emi-loan-id').value;
        var errorDiv = document.getElementById('emi-error');
        var btn = document.getElementById('emiBtn');

        if (!formData.get('amount_paid') || parseFloat(formData.get('amount_paid')) <= 0) {
            errorDiv.textContent = 'Please enter a valid payment amount';
            errorDiv.style.display = 'block';
            return;
        }

        errorDiv.style.display = 'none';
        isRecordingEmi = true;
        btn.disabled = true;
        btn.textContent = 'Recording...';

        fetch('/loans/' + loanId + '/record-emi/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': window.CSRF_TOKEN,
            },
            body: formData
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    window.location.reload();
                } else {
                    errorDiv.textContent = data.error || 'Error recording payment';
                    errorDiv.style.display = 'block';
                    isRecordingEmi = false;
                    btn.disabled = false;
                    btn.textContent = 'Record Payment';
                }
            })
            .catch(function (error) {
                errorDiv.textContent = 'Error: ' + error;
                errorDiv.style.display = 'block';
                isRecordingEmi = false;
                btn.disabled = false;
                btn.textContent = 'Record Payment';
            });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose public API
    window.LoansModule = {
        showLoanModal: showLoanModal,
        closeLoanModal: closeLoanModal,
        switchLoanTab: switchLoanTab,
        showAddLoanModal: showAddLoanModal,
        closeAddLoanModal: closeAddLoanModal,
        addLoan: addLoan,
        showApproveDialog: showApproveDialog,
        closeApproveDialog: closeApproveDialog,
        approveLoan: approveLoan,
        showRecordEmiDialog: showRecordEmiDialog,
        closeEmiDialog: closeEmiDialog,
        recordEmiPayment: recordEmiPayment,
        toggleDropdown: toggleDropdown
    };

    // Also expose as globals for onclick handlers in HTML
    window.showLoanModal = showLoanModal;
    window.closeLoanModal = closeLoanModal;
    window.switchLoanTab = switchLoanTab;
    window.showAddLoanModal = showAddLoanModal;
    window.closeAddLoanModal = closeAddLoanModal;
    window.addLoan = addLoan;
    window.showApproveDialog = showApproveDialog;
    window.showApproveDialogFromModal = showApproveDialogFromModal;
    window.closeApproveDialog = closeApproveDialog;
    window.approveLoan = approveLoan;
    window.showRecordEmiFromMenu = showRecordEmiFromMenu;
    window.showRecordEmiDialog = showRecordEmiDialog;
    window.closeEmiDialog = closeEmiDialog;
    window.recordEmiPayment = recordEmiPayment;
    window.toggleDropdown = toggleDropdown;

})();
