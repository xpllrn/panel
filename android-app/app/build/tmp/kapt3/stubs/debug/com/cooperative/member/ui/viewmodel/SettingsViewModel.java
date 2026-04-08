package com.cooperative.member.ui.viewmodel;

import androidx.lifecycle.ViewModel;
import com.cooperative.member.data.preferences.ThemeManager;
import com.cooperative.member.data.preferences.ThemeMode;
import dagger.hilt.android.lifecycle.HiltViewModel;
import kotlinx.coroutines.flow.SharingStarted;
import kotlinx.coroutines.flow.StateFlow;
import javax.inject.Inject;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000&\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0002\b\u0007\u0018\u00002\u00020\u0001B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J\u000e\u0010\n\u001a\u00020\u000b2\u0006\u0010\f\u001a\u00020\u0007R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0017\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\b\u0010\t\u00a8\u0006\r"}, d2 = {"Lcom/cooperative/member/ui/viewmodel/SettingsViewModel;", "Landroidx/lifecycle/ViewModel;", "themeManager", "Lcom/cooperative/member/data/preferences/ThemeManager;", "(Lcom/cooperative/member/data/preferences/ThemeManager;)V", "themeMode", "Lkotlinx/coroutines/flow/StateFlow;", "Lcom/cooperative/member/data/preferences/ThemeMode;", "getThemeMode", "()Lkotlinx/coroutines/flow/StateFlow;", "setThemeMode", "", "mode", "app_debug"})
@dagger.hilt.android.lifecycle.HiltViewModel()
public final class SettingsViewModel extends androidx.lifecycle.ViewModel {
    @org.jetbrains.annotations.NotNull()
    private final com.cooperative.member.data.preferences.ThemeManager themeManager = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.data.preferences.ThemeMode> themeMode = null;
    
    @javax.inject.Inject()
    public SettingsViewModel(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.preferences.ThemeManager themeManager) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.data.preferences.ThemeMode> getThemeMode() {
        return null;
    }
    
    public final void setThemeMode(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.preferences.ThemeMode mode) {
    }
}