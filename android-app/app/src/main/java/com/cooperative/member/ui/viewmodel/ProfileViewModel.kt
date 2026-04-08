package com.cooperative.member.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.data.model.MemberProfile
import com.cooperative.member.data.repository.MemberRepository
import com.cooperative.member.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val memberRepository: MemberRepository
) : ViewModel() {
    
    private val _profileState = MutableStateFlow<Resource<MemberProfile>?>(null)
    val profileState: StateFlow<Resource<MemberProfile>?> = _profileState
    
    init {
        loadProfile()
    }
    
    fun loadProfile() {
        viewModelScope.launch {
            _profileState.value = Resource.Loading()
            _profileState.value = memberRepository.getProfile()
        }
    }
}
