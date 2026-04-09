package com.cooperative.member.data

class MemberRepository(
    private val api: ApiService,
    private val session: SessionManager
) {

    suspend fun login(username: String, password: String): Result<MemberProfile> = runCatching {
        val resp = api.login(LoginRequest(username, password))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        val tokens = resp.body()!!
        session.saveTokens(tokens.access, tokens.refresh)

        val profile = api.getProfile()
        if (!profile.isSuccessful) throw ApiException(profile.code(), "Failed to fetch profile")
        profile.body()!!
    }

    suspend fun getDashboard(): Result<DashboardResponse> = apiCall { api.getDashboard() }

    suspend fun getAccounts(): Result<List<Account>> = apiCall {
        api.getAccounts(pageSize = 100)
    }.map { it.results }

    suspend fun getAccountDetail(id: Int): Result<AccountDetailResponse> = apiCall {
        api.getAccountDetail(id)
    }

    suspend fun getLoans(): Result<List<Loan>> = apiCall {
        api.getLoans(pageSize = 100)
    }.map { it.results }

    suspend fun getLoanDetail(id: Int): Result<LoanDetailResponse> = apiCall {
        api.getLoanDetail(id)
    }

    suspend fun getProfile(): Result<MemberProfile> = apiCall { api.getProfile() }

    suspend fun getTransactions(): Result<List<Transaction>> = apiCall {
        api.getTransactions(pageSize = 50)
    }.map { it.results }

    suspend fun logout() {
        session.clearSession()
    }

    suspend fun setTheme(mode: String) {
        session.saveThemeMode(mode)
    }

    private suspend fun <T> apiCall(call: suspend () -> retrofit2.Response<T>): Result<T> =
        runCatching {
            val resp = call()
            if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
            resp.body()!!
        }

    private fun parseError(resp: retrofit2.Response<*>): String {
        return when (resp.code()) {
            401 -> "Invalid credentials"
            403 -> "Access denied"
            404 -> "Not found"
            else -> resp.message().ifBlank { "Something went wrong" }
        }
    }
}

class ApiException(val code: Int, override val message: String) : Exception(message)
