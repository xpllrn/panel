package com.cooperative.member.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.CooperativeApp
import com.cooperative.member.data.MemberProfile
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface LoginState {
    data object Idle : LoginState
    data object LoadingCredentials : LoginState
    data class OtpRequired(val challengeToken: String, val secondsLeft: Int) : LoginState
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
                    _state.value = LoginState.OtpRequired(token, 900)
                    startOtpTimer(token)
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
        _state.value = LoginState.VerifyingOtp
        viewModelScope.launch {
            repo.verifyLoginOtp(current.challengeToken, otp)
                .onSuccess { _state.value = LoginState.Success(it) }
                .onFailure {
                    _state.value = LoginState.Error(it.message ?: "OTP verification failed")
                    _state.value = LoginState.OtpRequired(current.challengeToken, current.secondsLeft)
                }
        }
    }

    fun resendOtp() {
        val current = _state.value
        if (current !is LoginState.OtpRequired) return
        viewModelScope.launch {
            repo.resendLoginOtp(current.challengeToken)
                .onSuccess {
                    _state.value = LoginState.OtpRequired(current.challengeToken, 900)
                    startOtpTimer(current.challengeToken)
                }
                .onFailure { _state.value = LoginState.Error(it.message ?: "Failed to resend OTP") }
        }
    }

    private fun startOtpTimer(challengeToken: String) {
        viewModelScope.launch {
            var remaining = 900
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
