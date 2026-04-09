package com.cooperative.member.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    @POST("auth/login/")
    suspend fun loginStart(@Body body: LoginRequest): Response<LoginStartResponse>

    @POST("auth/login/verify-otp/")
    suspend fun verifyLoginOtp(@Body body: LoginVerifyRequest): Response<LoginResponse>

    @POST("auth/login/resend-otp/")
    suspend fun resendLoginOtp(@Body body: LoginResendRequest): Response<GenericSuccessResponse>

    @POST("auth/refresh/")
    suspend fun refreshToken(@Body body: RefreshRequest): Response<RefreshResponse>

    @GET("auth/profile/")
    suspend fun getProfile(): Response<MemberProfile>

    @GET("member/dashboard/")
    suspend fun getDashboard(): Response<DashboardResponse>

    @GET("member/accounts/")
    suspend fun getAccounts(
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null
    ): Response<AccountsListResponse>

    @GET("member/accounts/{id}/")
    suspend fun getAccountDetail(@Path("id") id: Int): Response<AccountDetailResponse>

    @GET("member/loans/")
    suspend fun getLoans(
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null
    ): Response<LoansListResponse>

    @GET("member/loans/{id}/")
    suspend fun getLoanDetail(@Path("id") id: Int): Response<LoanDetailResponse>

    @GET("member/transactions/")
    suspend fun getTransactions(
        @Query("type") type: String? = null,
        @Query("account") accountId: Int? = null,
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null
    ): Response<TransactionsListResponse>

    @POST("member/devices/register/")
    suspend fun registerDevice(@Body body: DeviceTokenRequest): Response<GenericSuccessResponse>

    @POST("member/devices/unregister/")
    suspend fun unregisterDevice(@Body body: DeviceTokenRequest): Response<GenericSuccessResponse>

    @POST("member/push/preferences/")
    suspend fun updatePushPreferences(@Body body: PushPreferencesRequest): Response<PushPreferencesUpdateResponse>

    @POST("member/notifications/test-push/")
    suspend fun testPushNotification(): Response<TestPushResponse>

    @POST("email/change/request/")
    suspend fun requestEmailChange(@Body body: EmailChangeRequest): Response<EmailChangeResponse>

    @POST("email/change/confirm/")
    suspend fun confirmEmailChange(@Body body: EmailChangeConfirmRequest): Response<EmailChangeResponse>

    @POST("auth/profile/update/")
    suspend fun updateProfile(@Body body: ProfileUpdateRequest): Response<ProfileUpdateResponse>
}
