package com.cooperative.member.ui.viewmodel

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.data.model.MemberProfile
import com.cooperative.member.data.repository.AuthRepository
import com.cooperative.member.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {
    
    companion object {
        private const val TAG = "LoginViewModel"
    }
    
    private val _loginState = MutableStateFlow<Resource<MemberProfile>?>(null)
    val loginState: StateFlow<Resource<MemberProfile>?> = _loginState.asStateFlow()
    
    private val _isLoggedIn = MutableStateFlow(false)
    val isLoggedIn: StateFlow<Boolean> = _isLoggedIn.asStateFlow()
    
    init {
        checkLoginStatus()
    }
    
    private fun checkLoginStatus() {
        viewModelScope.launch {
            _isLoggedIn.value = authRepository.isLoggedIn()
            Log.d(TAG, "Login status checked: ${_isLoggedIn.value}")
        }
    }
    
    fun login(username: String, password: String) {
        viewModelScope.launch {
            Log.d(TAG, "Login initiated for username: $username")
            _loginState.value = Resource.Loading()
            _loginState.value = authRepository.login(username, password)
            
            when (val state = _loginState.value) {
                is Resource.Success -> {
                    _isLoggedIn.value = true
                    Log.d(TAG, "Login successful")
                }
                is Resource.Error -> {
                    Log.e(TAG, "Login failed: ${state.message}")
                }
                else -> {}
            }
        }
    }
    
    fun logout() {
        viewModelScope.launch {
            Log.d(TAG, "Logout initiated")
            authRepository.logout()
            _isLoggedIn.value = false
            _loginState.value = null
        }
    }
}
