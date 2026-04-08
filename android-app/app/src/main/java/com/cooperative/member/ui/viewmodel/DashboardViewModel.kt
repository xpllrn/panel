package com.cooperative.member.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.data.model.DashboardResponse
import com.cooperative.member.data.repository.MemberRepository
import com.cooperative.member.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val memberRepository: MemberRepository
) : ViewModel() {
    
    private val _dashboardState = MutableStateFlow<Resource<DashboardResponse>?>(null)
    val dashboardState: StateFlow<Resource<DashboardResponse>?> = _dashboardState.asStateFlow()
    
    init {
        loadDashboard()
    }
    
    fun loadDashboard() {
        viewModelScope.launch {
            _dashboardState.value = Resource.Loading()
            _dashboardState.value = memberRepository.getDashboard()
        }
    }
}
