package com.panels.danc.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.panels.danc.CooperativeApp
import com.panels.danc.data.MemberProfile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

data class UiMessage(val text: String, val isError: Boolean)

sealed interface ProfileState {
    data object Loading : ProfileState
    data class Ready(val profile: MemberProfile) : ProfileState
    data class Error(val message: String) : ProfileState
}

class ProfileViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = (app as CooperativeApp).repository
    private val session = (app as CooperativeApp).session

    private val _state = MutableStateFlow<ProfileState>(ProfileState.Loading)
    val state: StateFlow<ProfileState> = _state.asStateFlow()
    private val _emailChangeChallenge = MutableStateFlow<String?>(null)
    val emailChangeChallenge: StateFlow<String?> = _emailChangeChallenge.asStateFlow()
    private val _emailChangeMessage = MutableStateFlow<UiMessage?>(null)
    val emailChangeMessage: StateFlow<UiMessage?> = _emailChangeMessage.asStateFlow()
    private val _personalMessage = MutableStateFlow<UiMessage?>(null)
    val personalMessage: StateFlow<UiMessage?> = _personalMessage.asStateFlow()
    private val _isUpdatingPersonal = MutableStateFlow(false)
    val isUpdatingPersonal: StateFlow<Boolean> = _isUpdatingPersonal.asStateFlow()
    private val _isRequestingEmailOtp = MutableStateFlow(false)
    val isRequestingEmailOtp: StateFlow<Boolean> = _isRequestingEmailOtp.asStateFlow()
    private val _isVerifyingEmailOtp = MutableStateFlow(false)
    val isVerifyingEmailOtp: StateFlow<Boolean> = _isVerifyingEmailOtp.asStateFlow()

    private val _pushSaving = MutableStateFlow(false)
    val pushSaving: StateFlow<Boolean> = _pushSaving.asStateFlow()
    private val _testPushLoading = MutableStateFlow(false)
    val testPushLoading: StateFlow<Boolean> = _testPushLoading.asStateFlow()
    private val _pushUiMessage = MutableStateFlow<UiMessage?>(null)
    val pushUiMessage: StateFlow<UiMessage?> = _pushUiMessage.asStateFlow()

    private val _passwordChangeMessage = MutableStateFlow<UiMessage?>(null)
    val passwordChangeMessage: StateFlow<UiMessage?> = _passwordChangeMessage.asStateFlow()
    private val _isChangingPassword = MutableStateFlow(false)
    val isChangingPassword: StateFlow<Boolean> = _isChangingPassword.asStateFlow()

    val themeMode = session.themeMode

    init {
        loadProfile()
    }

    fun loadProfile() {
        _state.value = ProfileState.Loading
        viewModelScope.launch {
            repo.getProfile()
                .onSuccess { _state.value = ProfileState.Ready(it) }
                .onFailure { _state.value = ProfileState.Error(it.message ?: "Failed") }
        }
    }

    fun setTheme(mode: String) {
        viewModelScope.launch { repo.setTheme(mode) }
    }

    fun setPushNotifications(enabled: Boolean) {
        _pushSaving.value = true
        _pushUiMessage.value = null
        viewModelScope.launch {
            repo.updatePushPreferences(enabled)
                .onSuccess {
                    loadProfile()
                    _pushUiMessage.value = UiMessage(
                        if (enabled) "Push notifications on." else "Push notifications off.",
                        false
                    )
                }
                .onFailure {
                    _pushUiMessage.value = UiMessage(it.message ?: "Could not update notifications.", true)
                }
            _pushSaving.value = false
        }
    }

    fun sendDemoPushNotification() {
        _testPushLoading.value = true
        _pushUiMessage.value = null
        viewModelScope.launch {
            repo.sendTestPushNotification()
                .onSuccess { _pushUiMessage.value = UiMessage(it, false) }
                .onFailure { _pushUiMessage.value = UiMessage(it.message ?: "Test failed.", true) }
            _testPushLoading.value = false
        }
    }

    fun clearPushUiMessage() {
        _pushUiMessage.value = null
    }

    fun requestEmailChange(newEmail: String) {
        if (newEmail.isBlank()) {
            _emailChangeMessage.value = UiMessage("Please enter a new email address.", true)
            return
        }
        _isRequestingEmailOtp.value = true
        viewModelScope.launch {
            repo.requestEmailChange(newEmail.trim())
                .onSuccess {
                    _emailChangeChallenge.value = it.challenge_token
                    _emailChangeMessage.value = UiMessage(it.message ?: "OTP sent to new email.", false)
                }
                .onFailure { _emailChangeMessage.value = UiMessage(it.message ?: "Failed to request email change.", true) }
            _isRequestingEmailOtp.value = false
        }
    }

    fun confirmEmailChange(otp: String) {
        val challenge = _emailChangeChallenge.value
        if (challenge.isNullOrBlank()) {
            _emailChangeMessage.value = UiMessage("Start email change request again.", true)
            return
        }
        if (otp.length != 6) {
            _emailChangeMessage.value = UiMessage("Enter 6-digit OTP.", true)
            return
        }
        _isVerifyingEmailOtp.value = true
        viewModelScope.launch {
            repo.confirmEmailChange(challenge, otp.trim())
                .onSuccess {
                    _emailChangeChallenge.value = null
                    _emailChangeMessage.value = UiMessage(it.message ?: "Email updated successfully.", false)
                    loadProfile()
                }
                .onFailure { _emailChangeMessage.value = UiMessage(it.message ?: "Failed to verify OTP.", true) }
            _isVerifyingEmailOtp.value = false
        }
    }

    fun clearEmailChangeMessage() {
        _emailChangeMessage.value = null
    }

    fun resetEmailChangeFlow() {
        _emailChangeChallenge.value = null
        _emailChangeMessage.value = null
    }

    fun updatePersonalInfo(phone: String?, birthDate: String?) {
        _isUpdatingPersonal.value = true
        viewModelScope.launch {
            repo.updateProfile(
                mobilePrimary = phone?.trim()?.ifBlank { null },
                dateOfBirth = birthDate?.trim()?.ifBlank { null }
            ).onSuccess {
                _personalMessage.value = UiMessage(it.message ?: "Profile updated.", false)
                loadProfile()
            }.onFailure {
                _personalMessage.value = UiMessage(it.message ?: "Failed to update profile.", true)
            }
            _isUpdatingPersonal.value = false
        }
    }

    fun clearPersonalMessage() {
        _personalMessage.value = null
    }

    fun clearPasswordChangeMessage() {
        _passwordChangeMessage.value = null
    }

    fun changePassword(currentPassword: String, newPassword: String, confirmPassword: String) {
        when {
            currentPassword.isBlank() || newPassword.isBlank() -> {
                _passwordChangeMessage.value = UiMessage("Fill in all password fields.", true)
                return
            }
            newPassword != confirmPassword -> {
                _passwordChangeMessage.value = UiMessage("New password and confirmation do not match.", true)
                return
            }
            newPassword.length < 8 -> {
                _passwordChangeMessage.value = UiMessage("New password must be at least 8 characters.", true)
                return
            }
        }
        _isChangingPassword.value = true
        _passwordChangeMessage.value = null
        viewModelScope.launch {
            repo.changePassword(currentPassword, newPassword)
                .onSuccess {
                    _passwordChangeMessage.value = UiMessage(
                        "Password updated successfully. Please log in again.",
                        false
                    )
                    delay(1200)
                    repo.resetSessionAfterPasswordChange()
                }
                .onFailure {
                    _passwordChangeMessage.value = UiMessage(it.message ?: "Could not change password.", true)
                }
            _isChangingPassword.value = false
        }
    }

    fun logout() {
        viewModelScope.launch { repo.logout() }
    }
}
