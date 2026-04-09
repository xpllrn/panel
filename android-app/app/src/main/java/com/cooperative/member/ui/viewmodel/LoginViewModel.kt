package com.cooperative.member.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.CooperativeApp
import com.cooperative.member.data.MemberProfile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface LoginState {
    data object Idle : LoginState
    data object Loading : LoginState
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
        _state.value = LoginState.Loading
        viewModelScope.launch {
            repo.login(username.trim(), password)
                .onSuccess { _state.value = LoginState.Success(it) }
                .onFailure { _state.value = LoginState.Error(it.message ?: "Login failed") }
        }
    }

    fun clearError() {
        if (_state.value is LoginState.Error) _state.value = LoginState.Idle
    }
}
