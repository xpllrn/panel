package com.cooperative.member.data.model

data class Loan(
    val id: Int,
    val loan_number: String,
    val loan_type: String,
    val principal_amount: String,
    val interest_rate: String,
    val tenure_months: Int,
    val emi_amount: String,
    val outstanding_balance: String,
    val status: String,
    val application_date: String,
    val approval_date: String?,
    val disbursement_date: String?,
    val processing_fee: String
)

data class LoanDetail(
    val loan: Loan,
    val repayment_schedule: List<EMI>?
)

data class EMI(
    val installment_number: Int,
    val due_date: String,
    val principal_component: String,
    val interest_component: String,
    val total_emi: String,
    val outstanding_after: String,
    val payment_date: String?,
    val amount_paid: String?,
    val late_penalty: String?,
    val status: String
)

data class LoansListResponse(
    val count: Int,
    val next: String?,
    val previous: String?,
    val results: List<Loan>
)
