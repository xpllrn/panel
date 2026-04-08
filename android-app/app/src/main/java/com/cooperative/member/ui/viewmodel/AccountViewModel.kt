package com.cooperative.member.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.data.model.Account
import com.cooperative.member.data.model.AccountDetail
import com.cooperative.member.data.repository.MemberRepository
import com.cooperative.member.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AccountViewModel @Inject constructor(
    private val memberRepository: MemberRepository
) : ViewModel() {
    
    private val _accountsState = MutableStateFlow<Resource<List<Account>>?>(null)
    val accountsState: StateFlow<Resource<List<Account>>?> = _accountsState.asStateFlow()
    
    private val _accountDetailState = MutableStateFlow<Resource<AccountDetail>?>(null)
    val accountDetailState: StateFlow<Resource<AccountDetail>?> = _accountDetailState.asStateFlow()
    
    fun loadAccounts() {
        viewModelScope.launch {
            _accountsState.value = Resource.Loading()
            _accountsState.value = memberRepository.getAccounts()
        }
    }
    
    fun loadAccountDetail(accountId: Int) {
        viewModelScope.launch {
            _accountDetailState.value = Resource.Loading()
            _accountDetailState.value = memberRepository.getAccountDetail(accountId)
        }
    }
}
