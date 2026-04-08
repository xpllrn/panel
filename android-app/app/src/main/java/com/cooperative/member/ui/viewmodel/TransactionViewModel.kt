package com.cooperative.member.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.data.model.Transaction
import com.cooperative.member.data.repository.MemberRepository
import com.cooperative.member.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class TransactionViewModel @Inject constructor(
    private val memberRepository: MemberRepository
) : ViewModel() {
    
    private val _transactionsState = MutableStateFlow<Resource<List<Transaction>>?>(null)
    val transactionsState: StateFlow<Resource<List<Transaction>>?> = _transactionsState.asStateFlow()
    
    fun loadTransactions(type: String? = null, accountId: Int? = null) {
        viewModelScope.launch {
            _transactionsState.value = Resource.Loading()
            _transactionsState.value = memberRepository.getTransactions(type, accountId)
        }
    }
}
