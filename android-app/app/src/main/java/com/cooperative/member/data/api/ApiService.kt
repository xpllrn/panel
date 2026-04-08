package com.cooperative.member.data.api

import com.cooperative.member.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    
    @POST("auth/login/")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>
    
    @POST("auth/refresh/")
    suspend fun refreshToken(@Body request: RefreshRequest): Response<RefreshResponse>
    
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
    suspend fun getAccountDetail(@Path("id") id: Int): Response<AccountDetail>
    
    @GET("member/loans/")
    suspend fun getLoans(
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null
    ): Response<LoansListResponse>
    
    @GET("member/loans/{id}/")
    suspend fun getLoanDetail(@Path("id") id: Int): Response<LoanDetail>
    
    @GET("member/transactions/")
    suspend fun getTransactions(
        @Query("type") type: String? = null,
        @Query("account") accountId: Int? = null,
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null
    ): Response<TransactionsListResponse>
}

data class TransactionsListResponse(
    val count: Int,
    val next: String?,
    val previous: String?,
    val results: List<Transaction>
)
