package com.panels.danc.data

import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(private val sessionManager: SessionManager) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val path = chain.request().url.encodedPath
        if (path.contains("/auth/login/") || path.contains("/auth/refresh/")) {
            return chain.proceed(chain.request())
        }

        val token = TokenCache.accessToken ?: runBlocking { sessionManager.getAccessToken() }
        if (!token.isNullOrBlank()) {
            TokenCache.accessToken = token
        }

        val request = if (token.isNullOrBlank()) {
            chain.request()
        } else {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        }
        
        val response = chain.proceed(request)
        
        // If we get 401 Unauthorized, try to refresh the token
        if (response.code == 401 && !request.url.encodedPath.contains("/auth/refresh/")) {
            response.close()
            
            val refreshed = runBlocking {
                refreshAccessToken()
            }
            
            if (refreshed) {
                // Retry the request with new token
                val newRequest = request.newBuilder()
                    .header("Authorization", "Bearer ${TokenCache.accessToken}")
                    .build()
                return chain.proceed(newRequest)
            }
        }
        
        return response
    }
    
    private suspend fun refreshAccessToken(): Boolean {
        return try {
            val refreshToken = sessionManager.getRefreshToken() ?: return false
            
            // Create a new API client without auth interceptor to avoid recursion
            val apiService = ApiClient.createRefreshService()
            val response = apiService.refreshToken(RefreshRequest(refreshToken))
            
            if (response.isSuccessful && response.body() != null) {
                val newAccessToken = response.body()!!.access
                // Update tokens in cache and storage
                sessionManager.saveTokens(newAccessToken, refreshToken)
                true
            } else {
                // Refresh failed, clear session
                sessionManager.clearSession()
                false
            }
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }
}
