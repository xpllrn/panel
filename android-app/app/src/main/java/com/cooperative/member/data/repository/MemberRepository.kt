package com.cooperative.member.data.repository

import com.cooperative.member.data.api.ApiService
import com.cooperative.member.data.model.*
import com.cooperative.member.util.Resource
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MemberRepository @Inject constructor(
    private val apiService: ApiService
) {
    
    suspend fun getDashboard(): Resource<DashboardResponse> {
        return try {
            val response = apiService.getDashboard()
            if (response.isSuccessful && response.body() != null) {
                Resource.Success(response.body()!!)
            } else {
                Resource.Error(response.message() ?: "Failed to fetch dashboard")
            }
        } catch (e: java.net.UnknownHostException) {
            Resource.Error("No internet connection. Please check your network")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: java.net.SocketTimeoutException) {
            Resource.Error("Connection timeout. Please try again")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
    
    suspend fun getAccounts(): Resource<List<Account>> {
        return try {
            val response = apiService.getAccounts()
            if (response.isSuccessful && response.body() != null) {
                Resource.Success(response.body()!!.results)
            } else {
                Resource.Error(response.message() ?: "Failed to fetch accounts")
            }
        } catch (e: java.net.UnknownHostException) {
            Resource.Error("No internet connection")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
    
    suspend fun getAccountDetail(id: Int): Resource<AccountDetail> {
        return try {
            val response = apiService.getAccountDetail(id)
            if (response.isSuccessful && response.body() != null) {
                Resource.Success(response.body()!!)
            } else {
                Resource.Error(response.message() ?: "Failed to fetch account details")
            }
        } catch (e: java.net.UnknownHostException) {
            Resource.Error("No internet connection")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
    
    suspend fun getLoans(): Resource<List<Loan>> {
        return try {
            val response = apiService.getLoans()
            if (response.isSuccessful && response.body() != null) {
                Resource.Success(response.body()!!.results)
            } else {
                Resource.Error(response.message() ?: "Failed to fetch loans")
            }
        } catch (e: java.net.UnknownHostException) {
            Resource.Error("No internet connection")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
    
    suspend fun getLoanDetail(id: Int): Resource<LoanDetail> {
        return try {
            val response = apiService.getLoanDetail(id)
            if (response.isSuccessful && response.body() != null) {
                Resource.Success(response.body()!!)
            } else {
                Resource.Error(response.message() ?: "Failed to fetch loan details")
            }
        } catch (e: java.net.UnknownHostException) {
            Resource.Error("No internet connection")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
    
    suspend fun getTransactions(type: String? = null, accountId: Int? = null): Resource<List<Transaction>> {
        return try {
            val response = apiService.getTransactions(type = type, accountId = accountId)
            if (response.isSuccessful && response.body() != null) {
                Resource.Success(response.body()!!.results)
            } else {
                Resource.Error(response.message() ?: "Failed to fetch transactions")
            }
        } catch (e: java.net.UnknownHostException) {
            Resource.Error("No internet connection")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
    
    suspend fun getProfile(): Resource<MemberProfile> {
        return try {
            val response = apiService.getProfile()
            if (response.isSuccessful && response.body() != null) {
                Resource.Success(response.body()!!)
            } else {
                Resource.Error(response.message() ?: "Failed to fetch profile")
            }
        } catch (e: java.net.UnknownHostException) {
            Resource.Error("No internet connection. Please check your network")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: java.net.SocketTimeoutException) {
            Resource.Error("Connection timeout. Please try again")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
}
