package com.panels.danc.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.panels.danc.CooperativeApp
import com.panels.danc.data.DashboardResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface HomeState {
    data object Loading : HomeState
    data class Ready(val data: DashboardResponse) : HomeState
    data class Error(val message: String) : HomeState
}

class HomeViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = (app as CooperativeApp).repository

    private val _state = MutableStateFlow<HomeState>(HomeState.Loading)
    val state: StateFlow<HomeState> = _state.asStateFlow()
    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.value = HomeState.Loading
        viewModelScope.launch {
            repo.getDashboard()
                .onSuccess { _state.value = HomeState.Ready(it) }
                .onFailure { _state.value = HomeState.Error(it.message ?: "Failed to load") }
        }
    }

    fun refresh() {
        _isRefreshing.value = true
        viewModelScope.launch {
            repo.getDashboard()
                .onSuccess { _state.value = HomeState.Ready(it) }
                .onFailure { error ->
                    if (_state.value is HomeState.Loading) {
                        _state.value = HomeState.Error(error.message ?: "Failed to refresh")
                    }
                }
            _isRefreshing.value = false
        }
    }
}
