package com.cooperative.member.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    @POST("auth/login/")
    suspend fun login(@Body body: LoginRequest): Response<LoginResponse>

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
}
