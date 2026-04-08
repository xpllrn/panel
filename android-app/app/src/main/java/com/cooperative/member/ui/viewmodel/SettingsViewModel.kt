package com.cooperative.member.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cooperative.member.data.preferences.ThemeManager
import com.cooperative.member.data.preferences.ThemeMode
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val themeManager: ThemeManager
) : ViewModel() {
    
    val themeMode: StateFlow<ThemeMode> = themeManager.themeMode.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = ThemeMode.SYSTEM
    )
    
    fun setThemeMode(mode: ThemeMode) {
        viewModelScope.launch {
            themeManager.setThemeMode(mode)
        }
    }
}
