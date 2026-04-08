package com.cooperative.member.data.model

data class Account(
    val id: Int,
    val account_number: String,
    val account_type: String,
    val balance: String,
    val interest_rate: String,
    val opening_date: String,
    val maturity_date: String?,
    val status: String,
    val principal_amount: String?,
    val tenure_months: Int?
)

data class AccountDetail(
    val account: Account,
    val recent_transactions: List<Transaction>
)

data class AccountsListResponse(
    val count: Int,
    val next: String?,
    val previous: String?,
    val results: List<Account>
)
