package com.panels.danc.data

import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.tasks.await
import org.json.JSONObject

class MemberRepository(
    private val api: ApiService,
    private val session: SessionManager
) {

    suspend fun startLogin(username: String, password: String): Result<LoginStartResponse> = runCatching {
        val resp = api.loginStart(LoginRequest(username, password))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        resp.body()!!
    }

    suspend fun verifyLoginOtp(challengeToken: String, otp: String): Result<MemberProfile> = runCatching {
        val resp = api.verifyLoginOtp(LoginVerifyRequest(challengeToken, otp))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        val tokens = resp.body()!!
        session.saveTokens(tokens.access, tokens.refresh)
        syncFcmTokenToServer()

        val profile = api.getProfile()
        if (!profile.isSuccessful) throw ApiException(profile.code(), "Failed to fetch profile")
        profile.body()!!
    }

    suspend fun resendLoginOtp(challengeToken: String): Result<GenericSuccessResponse> = runCatching {
        val resp = api.resendLoginOtp(LoginResendRequest(challengeToken))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        resp.body()!!
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

    suspend fun getTransactionDetail(id: Int): Result<Transaction> = apiCall {
        api.getTransactionDetail(id)
    }

    suspend fun logout() {
        val token = session.getDeviceToken()
        if (!token.isNullOrBlank()) {
            runCatching { api.unregisterDevice(DeviceTokenRequest(token)) }
            session.clearDeviceToken()
        }
        session.clearSession()
    }

    suspend fun setTheme(mode: String) {
        session.saveThemeMode(mode)
    }

    suspend fun registerDeviceToken(token: String) {
        if (token.isBlank()) return
        session.saveDeviceToken(token)
        runCatching {
            api.registerDevice(DeviceTokenRequest(token = token, platform = "android"))
        }
    }

    /**
     * Fetch current FCM token and register with API. Call only when the user is authenticated
     * (e.g. after OTP login or when restoring a logged-in session).
     */
    suspend fun syncFcmTokenToServer() {
        runCatching {
            val token = FirebaseMessaging.getInstance().token.await()
            if (!token.isNullOrBlank()) {
                registerDeviceToken(token)
            }
        }
    }

    suspend fun updatePushPreferences(enabled: Boolean): Result<Unit> = runCatching {
        val resp = api.updatePushPreferences(PushPreferencesRequest(enabled))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        val body = resp.body()
        if (body == null || !body.success) {
            throw ApiException(resp.code(), body?.error ?: "Could not update push preference.")
        }
    }

    suspend fun sendTestPushNotification(): Result<String> = runCatching {
        val resp = api.testPushNotification()
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        val body = resp.body() ?: throw ApiException(0, "Empty response")
        if (!body.success) throw ApiException(0, body.error ?: "Test push failed.")
        body.message ?: "Test notification sent."
    }

    suspend fun requestEmailChange(newEmail: String): Result<EmailChangeResponse> = runCatching {
        val resp = api.requestEmailChange(EmailChangeRequest(newEmail))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        resp.body()!!
    }

    suspend fun confirmEmailChange(challengeToken: String, otp: String): Result<EmailChangeResponse> = runCatching {
        val resp = api.confirmEmailChange(EmailChangeConfirmRequest(challengeToken, otp))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        resp.body()!!
    }

    suspend fun updateProfile(mobilePrimary: String?, dateOfBirth: String?): Result<ProfileUpdateResponse> = runCatching {
        val resp = api.updateProfile(ProfileUpdateRequest(mobilePrimary, dateOfBirth))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        resp.body()!!
    }

    suspend fun changePassword(currentPassword: String, newPassword: String): Result<GenericSuccessResponse> = runCatching {
        val resp = api.changePassword(PasswordChangeRequest(currentPassword, newPassword))
        if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
        val body = resp.body() ?: throw ApiException(0, "Empty response")
        if (!body.success) throw ApiException(0, body.error ?: "Could not change password.")
        body
    }

    suspend fun resetSessionAfterPasswordChange() {
        logout()
    }

    private suspend fun <T> apiCall(call: suspend () -> retrofit2.Response<T>): Result<T> =
        runCatching {
            val resp = call()
            if (resp.code() == 401) {
                // Access token is invalid/expired; clear local session so app returns to login.
                session.clearSession()
            }
            if (!resp.isSuccessful) throw ApiException(resp.code(), parseError(resp))
            resp.body()!!
        }

    private fun parseError(resp: retrofit2.Response<*>): String {
        val detail = parseErrorDetail(resp)

        if (!detail.isNullOrBlank()) {
            val normalized = detail.lowercase()
            if (normalized.contains("no active account")) {
                return "Your account is inactive. Please contact the branch/admin."
            }
            if (normalized.contains("invalid") || normalized.contains("credentials")) {
                return "Invalid username or password."
            }
            return detail
        }

        return when (resp.code()) {
            400, 401 -> "Invalid username or password."
            403 -> "Access denied"
            404 -> "Not found"
            else -> resp.message().ifBlank { "Something went wrong" }
        }
    }

    private fun parseErrorDetail(resp: retrofit2.Response<*>): String? {
        return try {
            val raw = resp.errorBody()?.string()?.trim().orEmpty()
            if (raw.isBlank()) return null
            if (!raw.startsWith("{")) return raw

            val json = JSONObject(raw)
            when {
                json.has("detail") -> json.optString("detail")
                json.has("error") -> json.optString("error")
                json.has("message") -> json.optString("message")
                else -> raw
            }
        } catch (_: Exception) {
            null
        }
    }
}

class ApiException(val code: Int, override val message: String) : Exception(message)
