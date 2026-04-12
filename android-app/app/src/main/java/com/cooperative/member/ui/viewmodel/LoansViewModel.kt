package com.panels.danc.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.panels.danc.CooperativeApp
import com.panels.danc.data.Loan
import com.panels.danc.data.LoanDetailResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface LoansListState {
    data object Loading : LoansListState
    data class Ready(val loans: List<Loan>) : LoansListState
    data class Error(val message: String) : LoansListState
}

sealed interface LoanDetailState {
    data object Loading : LoanDetailState
    data class Ready(val detail: LoanDetailResponse) : LoanDetailState
    data class Error(val message: String) : LoanDetailState
}

class LoansViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = (app as CooperativeApp).repository

    private val _list = MutableStateFlow<LoansListState>(LoansListState.Loading)
    val list: StateFlow<LoansListState> = _list.asStateFlow()
    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    private val _detail = MutableStateFlow<LoanDetailState>(LoanDetailState.Loading)
    val detail: StateFlow<LoanDetailState> = _detail.asStateFlow()

    init {
        loadLoans()
    }

    fun loadLoans() {
        _list.value = LoansListState.Loading
        viewModelScope.launch {
            repo.getLoans()
                .onSuccess { _list.value = LoansListState.Ready(it) }
                .onFailure { _list.value = LoansListState.Error(it.message ?: "Failed") }
        }
    }

    fun refreshLoans() {
        _isRefreshing.value = true
        viewModelScope.launch {
            repo.getLoans()
                .onSuccess { _list.value = LoansListState.Ready(it) }
                .onFailure { error ->
                    if (_list.value is LoansListState.Loading) {
                        _list.value = LoansListState.Error(error.message ?: "Failed")
                    }
                }
            _isRefreshing.value = false
        }
    }

    fun loadDetail(id: Int) {
        _detail.value = LoanDetailState.Loading
        viewModelScope.launch {
            repo.getLoanDetail(id)
                .onSuccess { _detail.value = LoanDetailState.Ready(it) }
                .onFailure { _detail.value = LoanDetailState.Error(it.message ?: "Failed") }
        }
    }
}
