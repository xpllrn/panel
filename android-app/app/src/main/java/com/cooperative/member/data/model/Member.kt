package com.cooperative.member.data.model

data class MemberProfile(
    val id: Int,
    val username: String,
    val member_id: String?,
    val display_name: String,
    val first_name: String,
    val last_name: String,
    val email: String,
    val member_type: String,
    val status: String,
    val share_capital_amount: String,
    val number_of_shares: Int,
    val dividend_payable_balance: String
)

data class DashboardResponse(
    val member: MemberInfo,
    val total_accounts: Int,
    val total_balance: String,
    val total_active_loans: Int,
    val total_outstanding: String,
    val share_capital: String,
    val dividend_payable: String,
    val accounts: List<AccountSummary>,
    val active_loans: List<LoanSummary>,
    val recent_transactions: List<Transaction>
)

data class MemberInfo(
    val member_id: String,
    val display_name: String,
    val email: String,
    val mobile_primary: String?,
    val status: String
)

data class AccountSummary(
    val id: Int,
    val account_number: String,
    val account_type: String,
    val balance: String,
    val status: String
)

data class LoanSummary(
    val id: Int,
    val loan_number: String,
    val loan_type: String,
    val principal_amount: String,
    val outstanding_balance: String,
    val emi_amount: String,
    val status: String
)

data class Transaction(
    val id: Int,
    val receipt_number: String,
    val transaction_type: String,
    val amount: String,
    val balance_after: String,
    val payment_mode: String,
    val description: String?,
    val created_at: String
)
