package com.cooperative.member.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.data.model.Loan
import com.cooperative.member.data.model.LoanDetail
import com.cooperative.member.data.repository.MemberRepository
import com.cooperative.member.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LoanViewModel @Inject constructor(
    private val memberRepository: MemberRepository
) : ViewModel() {
    
    private val _loansState = MutableStateFlow<Resource<List<Loan>>?>(null)
    val loansState: StateFlow<Resource<List<Loan>>?> = _loansState.asStateFlow()
    
    private val _loanDetailState = MutableStateFlow<Resource<LoanDetail>?>(null)
    val loanDetailState: StateFlow<Resource<LoanDetail>?> = _loanDetailState.asStateFlow()
    
    fun loadLoans() {
        viewModelScope.launch {
            _loansState.value = Resource.Loading()
            _loansState.value = memberRepository.getLoans()
        }
    }
    
    fun loadLoanDetail(loanId: Int) {
        viewModelScope.launch {
            _loanDetailState.value = Resource.Loading()
            _loanDetailState.value = memberRepository.getLoanDetail(loanId)
        }
    }
}
