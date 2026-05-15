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
        loadVouchers();
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

