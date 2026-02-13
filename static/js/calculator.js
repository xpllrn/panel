/**
 * Banking Calculator module (global modal)
 * Handles EMI, FD, RD, and Loan Eligibility calculations
 */
(function () {
    'use strict';

    var calculatorModal;

    function init() {
        calculatorModal = document.getElementById('calculatorModal');

        if (calculatorModal) {
            window.addEventListener('click', function (event) {
                if (event.target === calculatorModal) closeCalculatorModal();
            });

            document.addEventListener('keydown', function (event) {
                if (event.key === 'Escape' && calculatorModal.classList.contains('show')) {
                    closeCalculatorModal();
                }
            });
        }
    }

    /**
     * Open calculator modal
     */
    function openCalculatorModal() {
        if (calculatorModal) calculatorModal.classList.add('show');
    }

    /**
     * Close calculator modal
     */
    function closeCalculatorModal() {
        if (calculatorModal) calculatorModal.classList.remove('show');
    }

    /**
     * Format number as Indian currency
     */
    function formatCurrency(amount) {
        var num = Math.round(amount * 100) / 100;
        var parts = num.toFixed(2).split('.');
        var intPart = parts[0];
        var decPart = parts[1];
        var lastThree = intPart.slice(-3);
        var otherParts = intPart.slice(0, -3);
        if (otherParts !== '' && otherParts !== '-') {
            lastThree = ',' + lastThree;
        }
        var formatted = otherParts.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree;
        return '\u20B9 ' + formatted + '.' + decPart;
    }

    /**
     * Switch calculator tab
     */
    function switchCalcTab(tabName) {
        var tabs = document.querySelectorAll('#calculatorModal .calc-tab');
        var panels = document.querySelectorAll('#calculatorModal .calc-panel');

        for (var i = 0; i < tabs.length; i++) {
            tabs[i].classList.remove('active');
        }
        for (var j = 0; j < panels.length; j++) {
            panels[j].classList.remove('active');
        }

        var selectedTab = document.querySelector('#calculatorModal .calc-tab[data-tab="' + tabName + '"]');
        var selectedPanel = document.getElementById('calc-tab-' + tabName);

        if (selectedTab) selectedTab.classList.add('active');
        if (selectedPanel) selectedPanel.classList.add('active');
    }

    /**
     * Get numeric value from input field
     */
    function getVal(id) {
        var el = document.getElementById(id);
        if (!el) return 0;
        var val = parseFloat(el.value);
        return isNaN(val) ? 0 : val;
    }

    /**
     * Set text content of element
     */
    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    /**
     * Calculate EMI using reducing balance method
     */
    function calcEMI() {
        var principal = getVal('calc-emi-principal');
        var annualRate = getVal('calc-emi-rate');
        var tenure = getVal('calc-emi-tenure');

        if (principal <= 0 || annualRate <= 0 || tenure <= 0) {
            alert('Please fill in all fields with valid values');
            return;
        }

        var monthlyRate = annualRate / 1200;
        var factor = Math.pow(1 + monthlyRate, tenure);
        var emi = principal * monthlyRate * factor / (factor - 1);
        var totalPayment = emi * tenure;
        var totalInterest = totalPayment - principal;

        setText('calc-emi-monthly', formatCurrency(emi));
        setText('calc-emi-total-interest', formatCurrency(totalInterest));
        setText('calc-emi-total-payment', formatCurrency(totalPayment));
        setText('calc-emi-principal-display', formatCurrency(principal));

        var principalPct = (principal / totalPayment) * 100;
        var interestPct = (totalInterest / totalPayment) * 100;
        var barPrincipal = document.getElementById('calc-emi-bar-principal');
        var barInterest = document.getElementById('calc-emi-bar-interest');
        if (barPrincipal) barPrincipal.style.width = principalPct.toFixed(1) + '%';
        if (barInterest) barInterest.style.width = interestPct.toFixed(1) + '%';

        document.getElementById('calc-emi-result').style.display = 'block';
    }

    /**
     * Calculate FD maturity amount with compound interest
     */
    function calcFD() {
        var principal = getVal('calc-fd-principal');
        var annualRate = getVal('calc-fd-rate');
        var tenureMonths = getVal('calc-fd-tenure');
        var compoundingEl = document.getElementById('calc-fd-compounding');
        var compoundingFreq = compoundingEl ? parseInt(compoundingEl.value) : 4;

        if (principal <= 0 || annualRate <= 0 || tenureMonths <= 0) {
            alert('Please fill in all fields with valid values');
            return;
        }

        var tenureYears = tenureMonths / 12;
        var rateDecimal = annualRate / 100;
        var maturityAmount = principal * Math.pow(1 + rateDecimal / compoundingFreq, compoundingFreq * tenureYears);
        var totalInterest = maturityAmount - principal;
        var effectiveRate = ((maturityAmount / principal - 1) / tenureYears) * 100;

        setText('calc-fd-maturity', formatCurrency(maturityAmount));
        setText('calc-fd-interest', formatCurrency(totalInterest));
        setText('calc-fd-principal-display', formatCurrency(principal));
        setText('calc-fd-effective-rate', effectiveRate.toFixed(2) + '% p.a.');

        document.getElementById('calc-fd-result').style.display = 'block';
    }

    /**
     * Calculate RD maturity amount
     */
    function calcRD() {
        var monthly = getVal('calc-rd-monthly');
        var annualRate = getVal('calc-rd-rate');
        var tenureMonths = getVal('calc-rd-tenure');

        if (monthly <= 0 || annualRate <= 0 || tenureMonths <= 0) {
            alert('Please fill in all fields with valid values');
            return;
        }

        var quarterlyRate = annualRate / 400;
        var totalAmount = 0;

        for (var i = 0; i < tenureMonths; i++) {
            var remainingMonths = tenureMonths - i;
            var remainingQuarters = remainingMonths / 3;
            totalAmount += monthly * Math.pow(1 + quarterlyRate, remainingQuarters);
        }

        var totalDeposited = monthly * tenureMonths;
        var totalInterest = totalAmount - totalDeposited;

        setText('calc-rd-maturity', formatCurrency(totalAmount));
        setText('calc-rd-interest', formatCurrency(totalInterest));
        setText('calc-rd-total-deposited', formatCurrency(totalDeposited));
        setText('calc-rd-monthly-display', formatCurrency(monthly));

        document.getElementById('calc-rd-result').style.display = 'block';
    }

    /**
     * Calculate loan eligibility based on income
     */
    function calcEligibility() {
        var income = getVal('calc-elig-income');
        var existingEMI = getVal('calc-elig-existing-emi');
        var annualRate = getVal('calc-elig-rate');
        var tenure = getVal('calc-elig-tenure');
        var ratioEl = document.getElementById('calc-elig-ratio');
        var maxRatio = ratioEl ? parseInt(ratioEl.value) : 50;

        if (income <= 0 || annualRate <= 0 || tenure <= 0) {
            alert('Please fill in all fields with valid values');
            return;
        }

        var maxEMI = (income * maxRatio / 100);
        var availableEMI = maxEMI - existingEMI;

        if (availableEMI <= 0) {
            alert('Your existing EMIs exceed the maximum allowed EMI limit');
            return;
        }

        var monthlyRate = annualRate / 1200;
        var factor = Math.pow(1 + monthlyRate, tenure);
        var maxLoan = availableEMI * (factor - 1) / (monthlyRate * factor);
        var totalInterest = (availableEMI * tenure) - maxLoan;

        setText('calc-elig-max-loan', formatCurrency(maxLoan));
        setText('calc-elig-max-emi', formatCurrency(maxEMI));
        setText('calc-elig-available-emi', formatCurrency(availableEMI));
        setText('calc-elig-total-interest', formatCurrency(totalInterest));

        document.getElementById('calc-eligibility-result').style.display = 'block';
    }

    // Expose to global scope
    window.openCalculatorModal = openCalculatorModal;
    window.closeCalculatorModal = closeCalculatorModal;
    window.switchCalcTab = switchCalcTab;
    window.calcEMI = calcEMI;
    window.calcFD = calcFD;
    window.calcRD = calcRD;
    window.calcEligibility = calcEligibility;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
