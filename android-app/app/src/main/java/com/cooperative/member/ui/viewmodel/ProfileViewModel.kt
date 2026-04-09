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

sealed interface ProfileState {
    data object Loading : ProfileState
    data class Ready(val profile: MemberProfile) : ProfileState
    data class Error(val message: String) : ProfileState
}

class ProfileViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = (app as CooperativeApp).repository
    private val session = (app as CooperativeApp).session

    private val _state = MutableStateFlow<ProfileState>(ProfileState.Loading)
    val state: StateFlow<ProfileState> = _state.asStateFlow()

    val themeMode = session.themeMode

    init {
        loadProfile()
    }

    fun loadProfile() {
        _state.value = ProfileState.Loading
        viewModelScope.launch {
            repo.getProfile()
                .onSuccess { _state.value = ProfileState.Ready(it) }
                .onFailure { _state.value = ProfileState.Error(it.message ?: "Failed") }
        }
    }

    fun setTheme(mode: String) {
        viewModelScope.launch { repo.setTheme(mode) }
    }

    fun logout() {
        viewModelScope.launch { repo.logout() }
    }
}
