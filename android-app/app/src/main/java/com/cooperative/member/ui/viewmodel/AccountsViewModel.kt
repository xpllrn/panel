package com.panels.danc.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.panels.danc.CooperativeApp
import com.panels.danc.data.Account
import com.panels.danc.data.AccountDetailResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface AccountsListState {
    data object Loading : AccountsListState
    data class Ready(val accounts: List<Account>) : AccountsListState
    data class Error(val message: String) : AccountsListState
}

sealed interface AccountDetailState {
    data object Loading : AccountDetailState
    data class Ready(val detail: AccountDetailResponse) : AccountDetailState
    data class Error(val message: String) : AccountDetailState
}

class AccountsViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = (app as CooperativeApp).repository

    private val _list = MutableStateFlow<AccountsListState>(AccountsListState.Loading)
    val list: StateFlow<AccountsListState> = _list.asStateFlow()

    private val _detail = MutableStateFlow<AccountDetailState>(AccountDetailState.Loading)
    val detail: StateFlow<AccountDetailState> = _detail.asStateFlow()

    init {
        loadAccounts()
    }

    fun loadAccounts() {
        _list.value = AccountsListState.Loading
        viewModelScope.launch {
            repo.getAccounts()
                .onSuccess { _list.value = AccountsListState.Ready(it) }
                .onFailure { _list.value = AccountsListState.Error(it.message ?: "Failed") }
        }
    }

    fun loadDetail(id: Int) {
        _detail.value = AccountDetailState.Loading
        viewModelScope.launch {
            repo.getAccountDetail(id)
                .onSuccess { _detail.value = AccountDetailState.Ready(it) }
                .onFailure { _detail.value = AccountDetailState.Error(it.message ?: "Failed") }
        }
    }
}
