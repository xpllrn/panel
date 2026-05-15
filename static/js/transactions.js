/**
 * Transactions module — redesigned for per-line payment modes.
 * Each receipt line can have its own account, type, amount, AND payment method.
 */
(function () {
    'use strict';

    // State
    var isAddingReceipt = false;
    var searchTimeout = null;
    var selectedMemberAccounts = [];
    var selectedMemberPendingEmis = [];
    var lineCounter = 0;

    // DOM Elements (cached on init)
    var receiptModal, addReceiptModal;

    var PAYMENT_MODES = [
        { value: 'cash', label: 'Cash' },
        { value: 'cheque', label: 'Cheque' },
        { value: 'dd', label: 'Demand Draft' },
        { value: 'online', label: 'Online Transfer' },
        { value: 'neft', label: 'NEFT' },
        { value: 'rtgs', label: 'RTGS' },
        { value: 'upi', label: 'UPI' },
        { value: 'imps', label: 'IMPS' },
        { value: 'internal', label: 'Internal Transfer' }
    ];

    function escapeHTML(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatCurrency(amount) {
        var num = parseFloat(amount);
        if (isNaN(num)) return '0.00';
        return new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    }

    function init() {
        receiptModal = document.getElementById('receiptModal');
        addReceiptModal = document.getElementById('addReceiptModal');
        setupEventListeners();
    }

    function setupEventListeners() {
        window.addEventListener('click', function (event) {
            if (event.target === receiptModal) closeReceiptModal();
            if (event.target === addReceiptModal) closeAddReceiptModal();
            if (!event.target.matches('.kebab-menu')) {
                document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
                    menu.classList.remove('show');
                });
            }
            var memberSelector = document.querySelector('.member-selector');
            if (memberSelector && !memberSelector.contains(event.target)) {
                var results = document.getElementById('receipt-member-results');
                if (results) results.style.display = 'none';
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeReceiptModal();
                closeAddReceiptModal();
            }
        });

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

    // =========================================================
    // Receipt View Modal (unchanged logic)
    // =========================================================

    function applyReceiptToModal(receipt) {
        document.getElementById('modal-receipt-number').textContent = receipt.receipt_number;
        document.getElementById('modal-receipt-date').textContent = receipt.created_at || receipt.created_date || '-';
        document.getElementById('modal-payment-mode').textContent = receipt.payment_mode_display || '-';

        var titleEl = document.getElementById('modal-receipt-title');
        if (titleEl) {
            var typeUpper = (receipt.transaction_type || '').toUpperCase();
            if (typeUpper === 'CREDIT') titleEl.textContent = 'CREDIT RECEIPT';
            else if (typeUpper === 'DEBIT') titleEl.textContent = 'DEBIT RECEIPT';
            else titleEl.textContent = 'RECEIPT';
        }

        document.getElementById('modal-member-name').textContent = receipt.member_name || '-';
        document.getElementById('modal-member-id').textContent = receipt.member_id || '-';
        document.getElementById('modal-member-mobile').textContent = receipt.member_mobile || '-';
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

        var inst = receipt.instrument;
        var instSec = document.getElementById('modal-instrument-section');
        var instBody = document.getElementById('modal-instrument-body');
        if (inst && instSec && instBody) {
            var lines = [];
            lines.push('<strong>' + escapeHTML(inst.instrument_type_display || inst.instrument_type || '') + '</strong>');
            if (inst.amount) lines.push('Instrument amount: \u20B9 ' + formatCurrency(inst.amount));
            if (inst.cheque_number) lines.push('Cheque / DD no.: ' + escapeHTML(inst.cheque_number));
            if (inst.drawer_name) lines.push('Drawer: ' + escapeHTML(inst.drawer_name));
            if (inst.drawer_bank) lines.push('Bank: ' + escapeHTML(inst.drawer_bank));
            if (inst.drawer_ifsc) lines.push('IFSC: ' + escapeHTML(inst.drawer_ifsc));
            if (inst.cheque_date) lines.push('Cheque date: ' + escapeHTML(inst.cheque_date));
            if (inst.cheque_status) lines.push('Cheque status: ' + escapeHTML(inst.cheque_status));
            if (inst.reference_number) lines.push('UTR / ref.: ' + escapeHTML(inst.reference_number));
            if (inst.upi_vpa) lines.push('UPI VPA: ' + escapeHTML(inst.upi_vpa));
            if (inst.is_cleared) lines.push('Cleared' + (inst.clearing_date ? ' on ' + escapeHTML(inst.clearing_date) : ''));
            if (inst.bounce_reason) lines.push('Bounce: ' + escapeHTML(inst.bounce_reason));
            instBody.innerHTML = lines.join('<br>');
            instSec.style.display = '';
        } else if (instSec) {
            instSec.style.display = 'none';
            if (instBody) instBody.innerHTML = '';
        }
    }

    function showReceiptModal(receiptId) {
        fetch('/transactions/' + receiptId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    applyReceiptToModal(data.receipt);
                    receiptModal.classList.add('show');
                } else {
                    alert('Error loading receipt: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) { alert('Error loading receipt: ' + error); });
    }

    function closeReceiptModal() {
        if (receiptModal) receiptModal.classList.remove('show');
    }

    // =========================================================
    // Add Receipt Modal — Per-line payment mode design
    // =========================================================

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

        selectedMemberAccounts = [];
        selectedMemberPendingEmis = [];
        lineCounter = 0;
        resetReceiptLines();

        var btn = document.getElementById('addReceiptBtn');
        if (btn) { btn.disabled = false; btn.textContent = 'Create Receipt'; }

        isAddingReceipt = false;
        addReceiptModal.classList.add('show');
        updateBatchTotal();
    }

    function closeAddReceiptModal() {
        if (addReceiptModal) addReceiptModal.classList.remove('show');
    }

    // =========================================================
    // Per-line instrument fields visibility
    // =========================================================

    function syncLineInstrumentFields(row) {
        var pmSelect = row.querySelector('.line-payment-mode');
        var instPanel = row.querySelector('.line-instrument-panel');
        if (!pmSelect || !instPanel) return;
        var pm = pmSelect.value;
        if (pm === 'cash' || pm === 'internal') {
            instPanel.style.display = 'none';
            return;
        }
        instPanel.style.display = '';
        var chequeBlock = instPanel.querySelector('.line-inst-cheque');
        var upiBlock = instPanel.querySelector('.line-inst-upi');
        var transferBlock = instPanel.querySelector('.line-inst-transfer');
        if (chequeBlock) chequeBlock.style.display = (pm === 'cheque' || pm === 'dd') ? '' : 'none';
        if (upiBlock) upiBlock.style.display = (pm === 'upi') ? '' : 'none';
        if (transferBlock) transferBlock.style.display = (pm === 'neft' || pm === 'rtgs' || pm === 'online' || pm === 'imps') ? '' : 'none';
    }

    function buildLineInstrumentPayload(row) {
        var pmSelect = row.querySelector('.line-payment-mode');
        var pm = pmSelect ? pmSelect.value : 'cash';
        if (pm === 'cash' || pm === 'internal') return null;
        var out = {};
        if (pm === 'cheque' || pm === 'dd') {
            var cq = row.querySelector('.line-inst-cheque-number');
            if (cq && cq.value.trim()) out.cheque_number = cq.value.trim();
            var dn = row.querySelector('.line-inst-drawer-name');
            if (dn && dn.value.trim()) out.drawer_name = dn.value.trim();
            var db = row.querySelector('.line-inst-drawer-bank');
            if (db && db.value.trim()) out.drawer_bank = db.value.trim();
            var dif = row.querySelector('.line-inst-drawer-ifsc');
            if (dif && dif.value.trim()) out.drawer_ifsc = dif.value.trim().toUpperCase();
            var cdt = row.querySelector('.line-inst-cheque-date');
            if (cdt && cdt.value) out.cheque_date = cdt.value;
            if (pm === 'dd') out.instrument_type = 'dd';
        } else if (pm === 'upi') {
            var vpa = row.querySelector('.line-inst-upi-vpa');
            if (vpa && vpa.value.trim()) out.upi_vpa = vpa.value.trim();
            var utr = row.querySelector('.line-inst-upi-ref');
            if (utr && utr.value.trim()) out.reference_number = utr.value.trim();
        } else {
            var utr2 = row.querySelector('.line-inst-bank-ref');
            if (utr2 && utr2.value.trim()) out.reference_number = utr2.value.trim();
            if (pm === 'imps') out.instrument_type = 'imps';
        }
        return Object.keys(out).length > 0 ? out : null;
    }

    function getLineReferenceNumber(row) {
        var pmSelect = row.querySelector('.line-payment-mode');
        var pm = pmSelect ? pmSelect.value : 'cash';
        if (pm === 'cheque' || pm === 'dd') {
            var cq = row.querySelector('.line-inst-cheque-number');
            return cq ? cq.value.trim() : '';
        } else if (pm === 'upi') {
            var utr = row.querySelector('.line-inst-upi-ref');
            return utr ? utr.value.trim() : '';
        } else if (pm === 'neft' || pm === 'rtgs' || pm === 'online' || pm === 'imps') {
            var utr2 = row.querySelector('.line-inst-bank-ref');
            return utr2 ? utr2.value.trim() : '';
        }
        return '';
    }

    // =========================================================
    // Receipt line management (per-line payment mode)
    // =========================================================

    function buildPaymentModeOptions() {
        var html = '';
        PAYMENT_MODES.forEach(function (m) {
            html += '<option value="' + m.value + '">' + escapeHTML(m.label) + '</option>';
        });
        return html;
    }

    function addReceiptLine() {
        var container = document.getElementById('receipt-lines-container');
        if (!container) return;
        lineCounter++;
        var idx = lineCounter;

        var row = document.createElement('div');
        row.className = 'receipt-line-item';
        row.setAttribute('data-line-index', idx);

        row.innerHTML = ''
            + '<div class="line-header">'
            + '  <span class="line-number">#' + idx + '</span>'
            + '  <button type="button" class="btn-line-remove" title="Remove line">&times;</button>'
            + '</div>'
            + '<div class="line-main-row">'
            + '  <div class="line-field">'
            + '    <label class="line-label">Account</label>'
            + '    <select class="form-input line-account-id" required></select>'
            + '  </div>'
            + '  <div class="line-field">'
            + '    <label class="line-label">Type</label>'
            + '    <select class="form-input line-transaction-type" required>'
            + '      <option value="credit">Credit</option>'
            + '      <option value="debit">Debit</option>'
            + '      <option value="loan_emi">Loan EMI</option>'
            + '      <option value="interest">Interest Payment</option>'
            + '      <option value="dividend">Dividend</option>'
            + '      <option value="share_capital">Share Capital</option>'
            + '      <option value="transfer">Transfer</option>'
            + '    </select>'
            + '  </div>'
            + '  <div class="line-field">'
            + '    <label class="line-label">Amount (₹)</label>'
            + '    <input type="number" class="form-input line-amount" step="0.01" min="0.01" placeholder="0.00" required>'
            + '  </div>'
            + '  <div class="line-field">'
            + '    <label class="line-label">Payment Mode</label>'
            + '    <select class="form-input line-payment-mode">' + buildPaymentModeOptions() + '</select>'
            + '  </div>'
            + '</div>'
            + '<div class="line-emi-row" style="display:none;">'
            + '  <select class="form-input line-emi-id"><option value="">Select pending EMI</option></select>'
            + '</div>'
            + '<div class="line-instrument-panel" style="display:none;">'
            + '  <div class="line-inst-cheque" style="display:none;">'
            + '    <div class="inst-fields-grid">'
            + '      <input type="text" class="form-input form-input-sm line-inst-cheque-number" placeholder="Cheque / DD No." maxlength="30">'
            + '      <input type="text" class="form-input form-input-sm line-inst-drawer-name" placeholder="Drawer name" maxlength="200">'
            + '      <input type="text" class="form-input form-input-sm line-inst-drawer-bank" placeholder="Bank name" maxlength="200">'
            + '      <input type="text" class="form-input form-input-sm line-inst-drawer-ifsc" placeholder="IFSC" maxlength="11">'
            + '      <input type="date" class="form-input form-input-sm line-inst-cheque-date">'
            + '    </div>'
            + '  </div>'
            + '  <div class="line-inst-upi" style="display:none;">'
            + '    <div class="inst-fields-grid">'
            + '      <input type="text" class="form-input form-input-sm line-inst-upi-vpa" placeholder="UPI VPA (e.g. name@upi)" maxlength="100">'
            + '      <input type="text" class="form-input form-input-sm line-inst-upi-ref" placeholder="UTR / Reference" maxlength="100">'
            + '    </div>'
            + '  </div>'
            + '  <div class="line-inst-transfer" style="display:none;">'
            + '    <div class="inst-fields-grid">'
            + '      <input type="text" class="form-input form-input-sm line-inst-bank-ref" placeholder="UTR / Bank Reference" maxlength="100">'
            + '    </div>'
            + '  </div>'
            + '</div>';

        container.appendChild(row);
        renderLineAccountOptions();

        // Event listeners
        var typeSelect = row.querySelector('.line-transaction-type');
        var accountSelect = row.querySelector('.line-account-id');
        var pmSelect = row.querySelector('.line-payment-mode');
        var amountInput = row.querySelector('.line-amount');
        var removeBtn = row.querySelector('.btn-line-remove');

        if (typeSelect) typeSelect.addEventListener('change', function () { toggleLineEmiSelector(row); });
        if (accountSelect) accountSelect.addEventListener('change', function () { toggleLineEmiSelector(row); });
        if (pmSelect) pmSelect.addEventListener('change', function () { syncLineInstrumentFields(row); });
        if (amountInput) amountInput.addEventListener('input', function () { updateBatchTotal(); });
        if (removeBtn) removeBtn.addEventListener('click', function () { removeReceiptLine(removeBtn); });

        toggleLineEmiSelector(row);
        syncLineInstrumentFields(row);
        updateBatchTotal();
    }

    function removeReceiptLine(button) {
        var container = document.getElementById('receipt-lines-container');
        if (!container) return;
        if (container.querySelectorAll('.receipt-line-item').length <= 1) return;
        button.closest('.receipt-line-item').remove();
        updateBatchTotal();
    }

    function resetReceiptLines() {
        var container = document.getElementById('receipt-lines-container');
        if (!container) return;
        container.innerHTML = '';
        addReceiptLine();
    }

    function updateBatchTotal() {
        var rows = document.querySelectorAll('.receipt-line-item');
        var total = 0;
        rows.forEach(function (row) {
            var amt = row.querySelector('.line-amount');
            if (amt && amt.value) total += parseFloat(amt.value) || 0;
        });
        var el = document.getElementById('batch-total-amount');
        if (el) el.textContent = '\u20B9 ' + formatCurrency(total);
    }

    // =========================================================
    // Account options & EMI selectors
    // =========================================================

    function renderLineAccountOptions() {
        document.querySelectorAll('.line-account-id').forEach(function (select) {
            var current = select.value;
            var html = '<option value="">Select account...</option>';
            selectedMemberAccounts.forEach(function (account) {
                html += '<option value="' + escapeHTML(String(account.id)) + '">'
                    + escapeHTML(account.account_number) + ' (' + escapeHTML(account.account_type_display)
                    + ' \u2022 \u20B9' + formatCurrency(account.balance) + ')</option>';
            });
            select.innerHTML = html;
            if (current) select.value = current;
        });
    }

    function refreshLineEmiSelectors() {
        document.querySelectorAll('.receipt-line-item').forEach(function (row) {
            toggleLineEmiSelector(row);
        });
    }

    function toggleLineEmiSelector(row) {
        var typeSelect = row.querySelector('.line-transaction-type');
        var emiRow = row.querySelector('.line-emi-row');
        var emiSelect = row.querySelector('.line-emi-id');
        var accountSelect = row.querySelector('.line-account-id');
        if (!typeSelect || !emiRow || !emiSelect || !accountSelect) return;

        var isLoanEmi = typeSelect.value === 'loan_emi';
        if (!isLoanEmi) {
            emiRow.style.display = 'none';
            emiSelect.required = false;
            emiSelect.value = '';
            return;
        }

        var accountId = accountSelect.value;
        var available = selectedMemberPendingEmis.filter(function (emi) {
            return !emi.account_id || String(emi.account_id) === String(accountId);
        });

        emiSelect.innerHTML = '<option value="">Select pending EMI</option>';
        available.forEach(function (emi) {
            var label = emi.loan_number + ' | EMI #' + emi.installment_number + ' | \u20B9' + emi.amount_due + ' | Due ' + emi.due_date;
            emiSelect.innerHTML += '<option value="' + escapeHTML(String(emi.id)) + '">' + escapeHTML(label) + '</option>';
        });
        emiRow.style.display = '';
        emiSelect.required = true;
    }

    // =========================================================
    // Collect lines for submission
    // =========================================================

    function collectReceiptLines() {
        var rows = document.querySelectorAll('.receipt-line-item');
        var lines = [];
        rows.forEach(function (row) {
            var accountId = row.querySelector('.line-account-id').value;
            var transactionType = row.querySelector('.line-transaction-type').value;
            var amount = row.querySelector('.line-amount').value;
            var pmSelect = row.querySelector('.line-payment-mode');
            var emiSelect = row.querySelector('.line-emi-id');

            if (!accountId || !transactionType) return;
            var amountNum = parseFloat(amount);
            if (!amountNum || amountNum <= 0) return;

            var line = {
                account_id: accountId,
                transaction_type: transactionType,
                amount: amountNum.toFixed(2),
                description: '',
                payment_mode: pmSelect ? pmSelect.value : 'cash',
                reference_number: getLineReferenceNumber(row)
            };

            // Per-line instrument payload
            var instPayload = buildLineInstrumentPayload(row);
            if (instPayload) line.instrument_payload = instPayload;

            if (transactionType === 'loan_emi') {
                if (!emiSelect || !emiSelect.value) return;
                line.loan_repayment_id = emiSelect.value;
                line.description = 'Loan EMI payment';
            }
            lines.push(line);
        });
        return lines;
    }

    // =========================================================
    // Submit
    // =========================================================

    function addReceipt() {
        if (isAddingReceipt) return;

        var form = document.getElementById('addReceiptForm');
        var formData = new FormData(form);
        var errorDiv = document.getElementById('add-receipt-error');
        var btn = document.getElementById('addReceiptBtn');

        if (!formData.get('user_id')) {
            errorDiv.textContent = 'Please select a member';
            errorDiv.style.display = 'block';
            return;
        }

        var lines = collectReceiptLines();
        if (!lines.length) {
            errorDiv.textContent = 'Add at least one valid account entry with amount';
            errorDiv.style.display = 'block';
            return;
        }
        formData.set('account_entries', JSON.stringify(lines));

        // Use the first line's payment mode as the top-level fallback
        formData.set('payment_mode', lines[0].payment_mode || 'cash');

        errorDiv.style.display = 'none';
        isAddingReceipt = true;
        btn.disabled = true;
        btn.textContent = 'Creating...';

        fetch('/transactions/add/', {
            method: 'POST',
            headers: { 'X-CSRFToken': formData.get('csrfmiddlewaretoken') },
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

    // =========================================================
    // Member search & selection
    // =========================================================

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
                        if (member.member_id) display += ' (' + escapeHTML(member.member_id) + ')';
                        html += '<div class="member-selector-item" data-id="' + escapeHTML(String(member.id)) + '" data-name="' + escapeHTML(member.full_name || member.username) + '">' + display + '</div>';
                    });
                    resultsDiv.innerHTML = html;
                    resultsDiv.style.display = 'block';
                    resultsDiv.querySelectorAll('.member-selector-item').forEach(function (item) {
                        item.addEventListener('click', function () {
                            selectMember(this.getAttribute('data-id'), this.getAttribute('data-name'));
                        });
                    });
                } else {
                    resultsDiv.innerHTML = '<div class="member-selector-empty">No members found</div>';
                    resultsDiv.style.display = 'block';
                }
            })
            .catch(function (error) { console.error('Error searching members:', error); });
    }

    function selectMember(memberId, memberName) {
        document.getElementById('receipt-member-id').value = memberId;
        document.getElementById('receipt-member-search').value = memberName;
        var resultsDiv = document.getElementById('receipt-member-results');
        if (resultsDiv) resultsDiv.style.display = 'none';

        fetch('/api/members/' + memberId + '/accounts/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success && data.accounts.length > 0) {
                    selectedMemberAccounts = data.accounts;
                    selectedMemberPendingEmis = data.pending_emis || [];
                } else {
                    selectedMemberAccounts = [];
                    selectedMemberPendingEmis = [];
                }
                renderLineAccountOptions();
                refreshLineEmiSelectors();
            })
            .catch(function (error) {
                selectedMemberAccounts = [];
                selectedMemberPendingEmis = [];
                renderLineAccountOptions();
                refreshLineEmiSelectors();
                console.error('Error loading accounts:', error);
            });
    }

    // =========================================================
    // Vouchers
    // =========================================================

    function loadVouchers() {
        fetch('/transactions/vouchers/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                var body = document.getElementById('voucher-table-body');
                if (!body) return;
                if (!data.success || !data.vouchers || !data.vouchers.length) {
                    body.innerHTML = '<tr><td colspan="8" class="empty-state">No vouchers found</td></tr>';
                    return;
                }
                var html = '';
                var funds = window.RECEIPT_FUNDS || [];
                data.vouchers.forEach(function (voucher) {
                    var action = '-';
                    if (voucher.status === 'pending') {
                        var fundSelectId = 'voucher-fund-' + voucher.id;
                        var options = '<option value="">Select fund...</option>';
                        funds.forEach(function (fund) {
                            options += '<option value="' + escapeHTML(String(fund.id)) + '">' + escapeHTML(fund.name) + ' (' + escapeHTML(fund.type) + ')</option>';
                        });
                        action = '<div class="voucher-action-cell">'
                            + '<select id="' + fundSelectId + '" class="form-input voucher-fund-select">' + options + '</select>'
                            + '<button type="button" class="btn btn-primary btn-sm" onclick="transferVoucher(' + voucher.id + ', \'' + fundSelectId + '\')">Transfer</button>'
                            + '</div>';
                    }
                    var payCell = escapeHTML(voucher.payment_mode_display || voucher.payment_mode || '');
                    if (voucher.instrument_type) {
                        payCell += '<br><span class="voucher-instrument-hint">' + escapeHTML(voucher.instrument_type) + '</span>';
                    }
                    html += '<tr><td class="voucher-num">' + escapeHTML(voucher.voucher_number) + '</td>'
                        + '<td class="voucher-date">' + escapeHTML(voucher.created_at || '') + '</td>'
                        + '<td>' + escapeHTML(voucher.voucher_type_display || 'Voucher') + '</td>'
                        + '<td>' + escapeHTML(voucher.member_name) + '</td>'
                        + '<td class="voucher-col-amount">\u20B9' + escapeHTML(voucher.total_amount) + '</td>'
                        + '<td class="voucher-paymode">' + payCell + '</td>'
                        + '<td><span class="voucher-status">' + escapeHTML(voucher.status_display) + '</span></td>'
                        + '<td class="voucher-col-action">' + action + '</td></tr>';
                });
                body.innerHTML = html;
            })
            .catch(function () {
                var body = document.getElementById('voucher-table-body');
                if (body) body.innerHTML = '<tr><td colspan="8" class="empty-state" style="color:#b91c1c;">Could not load vouchers</td></tr>';
            });
    }

    function transferVoucher(voucherId, fundSelectId) {
        var selectEl = document.getElementById(fundSelectId);
        var fundId = selectEl ? selectEl.value : '';
        if (!fundId) return;
        var form = new FormData();
        form.append('fund_id', fundId);
        form.append('csrfmiddlewaretoken', window.CSRF_TOKEN);
        fetch('/transactions/vouchers/' + voucherId + '/transfer/', {
            method: 'POST',
            headers: { 'X-CSRFToken': window.CSRF_TOKEN },
            body: form
        }).then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) { alert(data.error || 'Transfer failed'); return; }
                loadVouchers();
                window.location.reload();
            });
    }

    // =========================================================
    // Dropdown & Print
    // =========================================================

    function toggleDropdown(event, receiptId) {
        event.stopPropagation();
        document.querySelectorAll('.dropdown-menu').forEach(function (menu) {
            if (menu.id !== 'dropdown-' + receiptId) menu.classList.remove('show');
        });
        document.getElementById('dropdown-' + receiptId).classList.toggle('show');
    }

    function printReceipt(event, receiptId) {
        event.stopPropagation();
        var dropdown = document.getElementById('dropdown-' + receiptId);
        if (dropdown) dropdown.classList.remove('show');
        fetch('/transactions/' + receiptId + '/get/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    applyReceiptToModal(data.receipt);
                    receiptModal.classList.add('show');
                    setTimeout(function () { window.print(); }, 300);
                } else {
                    alert('Error loading receipt: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function (error) { alert('Error loading receipt: ' + error); });
    }

    function printCurrentReceipt() { window.print(); }

    // =========================================================
    // Init
    // =========================================================

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    window.ReceiptsModule = {
        showReceiptModal: showReceiptModal,
        closeReceiptModal: closeReceiptModal,
        showAddReceiptModal: showAddReceiptModal,
        closeAddReceiptModal: closeAddReceiptModal,
        addReceipt: addReceipt,
        toggleDropdown: toggleDropdown,
        printReceipt: printReceipt,
        printCurrentReceipt: printCurrentReceipt,
        addReceiptLine: addReceiptLine,
        removeReceiptLine: removeReceiptLine,
        transferVoucher: transferVoucher
    };

    window.showReceiptModal = showReceiptModal;
    window.closeReceiptModal = closeReceiptModal;
    window.showAddReceiptModal = showAddReceiptModal;
    window.closeAddReceiptModal = closeAddReceiptModal;
    window.addReceipt = addReceipt;
    window.toggleDropdown = toggleDropdown;
    window.printReceipt = printReceipt;
    window.printCurrentReceipt = printCurrentReceipt;
    window.addReceiptLine = addReceiptLine;
    window.removeReceiptLine = removeReceiptLine;
    window.transferVoucher = transferVoucher;

})();
