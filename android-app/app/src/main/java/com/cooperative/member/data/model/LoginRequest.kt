package com.cooperative.member.data.model

data class LoginRequest(
    val username: String,
    val password: String
)

data class LoginResponse(
    val access: String,
    val refresh: String
)

data class RefreshRequest(
    val refresh: String
)

data class RefreshResponse(
    val access: String
)
