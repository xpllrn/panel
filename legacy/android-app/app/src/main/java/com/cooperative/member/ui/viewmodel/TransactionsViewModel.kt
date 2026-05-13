package com.panels.danc.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.panels.danc.CooperativeApp
import com.panels.danc.data.Transaction
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface TransactionDetailState {
    data object Loading : TransactionDetailState
    data class Ready(val detail: Transaction) : TransactionDetailState
    data class Error(val message: String) : TransactionDetailState
}

class TransactionsViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = (app as CooperativeApp).repository

    private val _detail = MutableStateFlow<TransactionDetailState>(TransactionDetailState.Loading)
    val detail: StateFlow<TransactionDetailState> = _detail.asStateFlow()

    fun loadDetail(id: Int) {
        _detail.value = TransactionDetailState.Loading
        viewModelScope.launch {
            repo.getTransactionDetail(id)
                .onSuccess { _detail.value = TransactionDetailState.Ready(it) }
                .onFailure { _detail.value = TransactionDetailState.Error(it.message ?: "Failed to load transaction.") }
        }
    }
}
