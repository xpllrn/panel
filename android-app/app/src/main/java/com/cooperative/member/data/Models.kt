package com.cooperative.member.data

// ── Auth ──

data class LoginRequest(val username: String, val password: String)
data class LoginResponse(val access: String, val refresh: String)
data class LoginStartResponse(
    val success: Boolean = false,
    val message: String = "",
    val challenge_token: String = "",
    val expires_in_seconds: Int = 0
)
data class LoginVerifyRequest(val challenge_token: String, val otp: String)
data class LoginResendRequest(val challenge_token: String)
data class RefreshRequest(val refresh: String)
data class RefreshResponse(val access: String)
data class GenericSuccessResponse(
    val success: Boolean = false,
    val message: String? = null,
    val error: String? = null
)
data class DeviceTokenRequest(val token: String, val platform: String = "android")
data class EmailChangeRequest(val new_email: String)
data class EmailChangeConfirmRequest(val challenge_token: String, val otp: String)
data class EmailChangeResponse(
    val success: Boolean = false,
    val message: String? = null,
    val challenge_token: String? = null,
    val expires_in_seconds: Int? = null,
    val email: String? = null,
    val error: String? = null
)
data class ProfileUpdateRequest(
    val mobile_primary: String? = null,
    val date_of_birth: String? = null
)
data class ProfileUpdateResponse(
    val success: Boolean = false,
    val message: String? = null,
    val profile: MemberProfile? = null,
    val error: String? = null
)

// ── Profile ──

data class MemberProfile(
    val id: Int = 0,
    val username: String = "",
    val member_id: String? = null,
    val display_name: String = "",
    val first_name: String = "",
    val last_name: String = "",
    val email: String = "",
    val email_verified: Boolean = false,
    val member_type: String = "",
    val status: String = "",
    val date_of_joining: String? = null,
    val date_of_birth: String? = null,
    val age: Int? = null,
    val gender: String? = null,
    val mobile_primary: String? = null,
    val current_city: String? = null,
    val current_state: String? = null,
    val share_capital_amount: String = "0.00",
    val number_of_shares: Int = 0,
    val dividend_payable_balance: String = "0.00",
    val push_notifications_enabled: Boolean = true
)

data class PushPreferencesRequest(val push_notifications_enabled: Boolean)

data class PushPreferencesUpdateResponse(
    val success: Boolean = false,
    val push_notifications_enabled: Boolean? = null,
    val error: String? = null
)

data class TestPushResponse(
    val success: Boolean = false,
    val message: String? = null,
    val delivered: Int? = null,
    val error: String? = null
)

// ── Dashboard ──

data class DashboardResponse(
    val member: MemberInfo = MemberInfo(),
    val total_accounts: Int = 0,
    val total_balance: String = "0.00",
    val total_active_loans: Int = 0,
    val total_outstanding: String = "0.00",
    val share_capital: String = "0.00",
    val dividend_payable: String = "0.00",
    val accounts: List<AccountSummary> = emptyList(),
    val active_loans: List<LoanSummary> = emptyList(),
    val recent_transactions: List<Transaction> = emptyList()
)

data class MemberInfo(
    val member_id: String? = null,
    val display_name: String = "",
    val email: String = "",
    val mobile_primary: String? = null,
    val status: String = ""
)

data class AccountSummary(
    val id: Int = 0,
    val account_number: String = "",
    val account_type: String = "",
    val balance: String = "0.00",
    val status: String = ""
)

data class LoanSummary(
    val id: Int = 0,
    val loan_number: String = "",
    val loan_type: String = "",
    val principal_amount: String = "0.00",
    val outstanding_balance: String = "0.00",
    val emi_amount: String = "0.00",
    val status: String = ""
)

data class Transaction(
    val id: Int = 0,
    val receipt_number: String = "",
    val transaction_type: String = "",
    val amount: String = "0.00",
    val balance_after: String = "0.00",
    val payment_mode: String? = null,
    val description: String? = null,
    val created_at: String = ""
)

// ── Accounts ──

data class Account(
    val id: Int = 0,
    val account_number: String = "",
    val account_type: String = "",
    val account_type_display: String? = null,
    val balance: String = "0.00",
    val interest_rate: String? = null,
    val principal_amount: String? = null,
    val opening_date: String? = null,
    val maturity_date: String? = null,
    val tenure_months: Int? = null,
    val status: String = "",
    val status_display: String? = null,
    val accrued_interest: String? = null,
    val nominee_name: String? = null,
    val created_at: String? = null
)

data class AccountsListResponse(
    val count: Int = 0,
    val next: String? = null,
    val previous: String? = null,
    val results: List<Account> = emptyList()
)

data class AccountDetailResponse(
    val id: Int = 0,
    val account_number: String = "",
    val account_type: String = "",
    val account_type_display: String? = null,
    val balance: String = "0.00",
    val interest_rate: String? = null,
    val principal_amount: String? = null,
    val opening_date: String? = null,
    val maturity_date: String? = null,
    val tenure_months: Int? = null,
    val status: String = "",
    val status_display: String? = null,
    val accrued_interest: String? = null,
    val nominee_name: String? = null,
    val transactions: List<Transaction> = emptyList()
)

// ── Loans ──

data class Loan(
    val id: Int = 0,
    val loan_number: String = "",
    val loan_type: String = "",
    val loan_type_display: String? = null,
    val principal_amount: String = "0.00",
    val interest_rate: String = "0.00",
    val tenure_months: Int = 0,
    val emi_amount: String = "0.00",
    val outstanding_balance: String = "0.00",
    val overdue_amount: String? = null,
    val status: String = "",
    val status_display: String? = null,
    val emis_paid: Int? = null,
    val total_emis: Int? = null,
    val completion_percentage: Double? = null,
    val is_npa: Boolean = false,
    val application_date: String? = null,
    val disbursement_date: String? = null
)

data class LoansListResponse(
    val count: Int = 0,
    val next: String? = null,
    val previous: String? = null,
    val results: List<Loan> = emptyList()
)

data class LoanDetailResponse(
    val id: Int = 0,
    val loan_number: String = "",
    val loan_type: String = "",
    val loan_type_display: String? = null,
    val principal_amount: String = "0.00",
    val interest_rate: String = "0.00",
    val interest_type: String? = null,
    val tenure_months: Int = 0,
    val emi_amount: String = "0.00",
    val total_payable: String? = null,
    val total_paid: String? = null,
    val outstanding_balance: String = "0.00",
    val overdue_amount: String? = null,
    val processing_fee: String? = null,
    val status: String = "",
    val status_display: String? = null,
    val application_date: String? = null,
    val approval_date: String? = null,
    val disbursement_date: String? = null,
    val first_emi_date: String? = null,
    val closure_date: String? = null,
    val total_emis: Int? = null,
    val emis_paid: Int? = null,
    val emis_overdue: Int? = null,
    val completion_percentage: Double? = null,
    val purpose: String? = null,
    val is_npa: Boolean = false,
    val repayments: List<LoanRepayment> = emptyList()
)

data class LoanRepayment(
    val id: Int = 0,
    val installment_number: Int = 0,
    val due_date: String = "",
    val paid_date: String? = null,
    val amount_due: String? = null,
    val amount_paid: String? = null,
    val principal_component: String? = null,
    val interest_component: String? = null,
    val penalty: String? = null,
    val balance_after: String? = null,
    val payment_status: String? = null,
    val payment_mode: String? = null
)

// ── Transactions ──

data class TransactionsListResponse(
    val count: Int = 0,
    val next: String? = null,
    val previous: String? = null,
    val results: List<Transaction> = emptyList()
)
