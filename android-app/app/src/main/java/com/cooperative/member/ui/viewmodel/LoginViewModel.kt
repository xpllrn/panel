package com.panels.danc.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.panels.danc.CooperativeApp
import com.panels.danc.data.MemberProfile
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface LoginState {
    data object Idle : LoginState
    data object LoadingCredentials : LoginState
    data class OtpRequired(val challengeToken: String, val secondsLeft: Int, val maskedEmail: String) : LoginState
    data object VerifyingOtp : LoginState
    data class Success(val profile: MemberProfile) : LoginState
    data class Error(val message: String) : LoginState
}

class LoginViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = (app as CooperativeApp).repository

    private val _state = MutableStateFlow<LoginState>(LoginState.Idle)
    val state: StateFlow<LoginState> = _state.asStateFlow()

    fun login(username: String, password: String) {
        if (username.isBlank() || password.isBlank()) {
            _state.value = LoginState.Error("Please enter both username and password")
            return
        }
        _state.value = LoginState.LoadingCredentials
        viewModelScope.launch {
            repo.startLogin(username.trim(), password)
                .onSuccess {
                    val token = it.challenge_token
                    val masked = it.email_masked?.takeIf { m -> m.isNotBlank() } ?: "your email"
                    val ttl = it.expires_in_seconds.takeIf { s -> s > 0 } ?: 900
                    _state.value = LoginState.OtpRequired(token, ttl, masked)
                    startOtpTimer(token, ttl)
                }
                .onFailure { _state.value = LoginState.Error(it.message ?: "Login failed") }
        }
    }

    fun verifyOtp(otp: String) {
        val current = _state.value
        if (current !is LoginState.OtpRequired) {
            _state.value = LoginState.Error("Start login again.")
            return
        }
        if (otp.length != 6) {
            _state.value = LoginState.Error("Enter 6-digit OTP.")
            return
        }
        val savedSeconds = current.secondsLeft
        val masked = current.maskedEmail
        val token = current.challengeToken
        _state.value = LoginState.VerifyingOtp
        viewModelScope.launch {
            repo.verifyLoginOtp(token, otp)
                .onSuccess { _state.value = LoginState.Success(it) }
                .onFailure {
                    _state.value = LoginState.OtpRequired(token, savedSeconds, masked)
                    startOtpTimer(token, savedSeconds)
                }
        }
    }

    fun resendOtp() {
        val current = _state.value
        if (current !is LoginState.OtpRequired) return
        viewModelScope.launch {
            repo.resendLoginOtp(current.challengeToken)
                .onSuccess { body ->
                    val masked = body.email_masked?.takeIf { it.isNotBlank() } ?: current.maskedEmail
                    val ttl = body.expires_in_seconds?.takeIf { it > 0 } ?: 900
                    _state.value = LoginState.OtpRequired(current.challengeToken, ttl, masked)
                    startOtpTimer(current.challengeToken, ttl)
                }
                .onFailure { _state.value = LoginState.Error(it.message ?: "Failed to resend OTP") }
        }
    }

    private fun startOtpTimer(challengeToken: String, initialSeconds: Int) {
        viewModelScope.launch {
            var remaining = initialSeconds.coerceAtLeast(0)
            while (remaining > 0) {
                delay(1000)
                remaining -= 1
                val current = _state.value
                if (current is LoginState.OtpRequired && current.challengeToken == challengeToken) {
                    _state.value = current.copy(secondsLeft = remaining)
                } else {
                    break
                }
            }
            val current = _state.value
            if (current is LoginState.OtpRequired && current.challengeToken == challengeToken && remaining <= 0) {
                _state.value = current.copy(secondsLeft = 0)
            }
        }
    }

    fun backToCredentials() {
        _state.value = LoginState.Idle
    }

    fun clearError() {
        if (_state.value is LoginState.Error) _state.value = LoginState.Idle
    }
}
