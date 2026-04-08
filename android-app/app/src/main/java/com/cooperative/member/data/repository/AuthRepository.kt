package com.cooperative.member.data.repository

import android.util.Log
import com.cooperative.member.data.api.ApiService
import com.cooperative.member.data.model.LoginRequest
import com.cooperative.member.data.model.MemberProfile
import com.cooperative.member.util.Resource
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
) {
    
    companion object {
        private const val TAG = "AuthRepository"
    }
    
    suspend fun login(username: String, password: String): Resource<MemberProfile> {
        return try {
            Log.d(TAG, "Attempting login for user: $username")
            val response = apiService.login(LoginRequest(username, password))
            
            Log.d(TAG, "Login response code: ${response.code()}")
            
            if (response.isSuccessful && response.body() != null) {
                val loginResponse = response.body()!!
                Log.d(TAG, "Login successful, saving tokens")
                tokenManager.saveTokens(loginResponse.access, loginResponse.refresh)
                
                // Get profile after login
                Log.d(TAG, "Fetching user profile")
                val profileResponse = apiService.getProfile()
                if (profileResponse.isSuccessful && profileResponse.body() != null) {
                    Log.d(TAG, "Profile fetched successfully")
                    Resource.Success(profileResponse.body()!!)
                } else {
                    Log.e(TAG, "Failed to fetch profile: ${profileResponse.code()}")
                    Resource.Error("Failed to fetch profile")
                }
            } else {
                val errorMsg = when (response.code()) {
                    401 -> "Invalid username or password"
                    404 -> "Server not found"
                    500 -> "Server error. Please try again later"
                    else -> "Login failed: ${response.message()}"
                }
                Log.e(TAG, "Login failed: $errorMsg (code: ${response.code()})")
                Resource.Error(errorMsg)
            }
        } catch (e: java.net.UnknownHostException) {
            Log.e(TAG, "UnknownHostException: ${e.message}")
            Resource.Error("No internet connection. Please check your network")
        } catch (e: java.net.ConnectException) {
            Log.e(TAG, "ConnectException: ${e.message}")
            Resource.Error("Cannot connect to server. Please check if server is running")
        } catch (e: java.net.SocketTimeoutException) {
            Log.e(TAG, "SocketTimeoutException: ${e.message}")
            Resource.Error("Connection timeout. Please try again")
        } catch (e: Exception) {
            Log.e(TAG, "Exception during login: ${e.javaClass.simpleName} - ${e.message}", e)
            Resource.Error("Network error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
    
    suspend fun logout() {
        tokenManager.clearTokens()
    }
    
    suspend fun isLoggedIn(): Boolean {
        return tokenManager.getAccessToken() != null
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
            Resource.Error("No internet connection")
        } catch (e: java.net.ConnectException) {
            Resource.Error("Cannot connect to server")
        } catch (e: java.net.SocketTimeoutException) {
            Resource.Error("Connection timeout")
        } catch (e: Exception) {
            Resource.Error("Error: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
}
