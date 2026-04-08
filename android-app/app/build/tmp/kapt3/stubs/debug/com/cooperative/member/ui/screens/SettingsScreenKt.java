package com.cooperative.member.ui.screens;

import androidx.compose.foundation.layout.*;
import androidx.compose.material.icons.Icons;
import androidx.compose.material.icons.filled.*;
import androidx.compose.material3.*;
import androidx.compose.runtime.*;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.text.font.FontWeight;
import com.cooperative.member.data.preferences.ThemeMode;
import com.cooperative.member.ui.viewmodel.SettingsViewModel;

@kotlin.Metadata(mv = {1, 9, 0}, k = 2, xi = 48, d1 = {"\u0000$\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\u001a\u0018\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u0003H\u0007\u001a\u0012\u0010\u0005\u001a\u00020\u00012\b\b\u0002\u0010\u0006\u001a\u00020\u0007H\u0007\u001a&\u0010\b\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\t\u001a\u00020\n2\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\u00010\fH\u0007\u00a8\u0006\r"}, d2 = {"SettingsRow", "", "title", "", "subtitle", "SettingsScreen", "viewModel", "Lcom/cooperative/member/ui/viewmodel/SettingsViewModel;", "ThemeOption", "selected", "", "onClick", "Lkotlin/Function0;", "app_debug"})
public final class SettingsScreenKt {
    
    @kotlin.OptIn(markerClass = {androidx.compose.material3.ExperimentalMaterial3Api.class})
    @androidx.compose.runtime.Composable()
    public static final void SettingsScreen(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.ui.viewmodel.SettingsViewModel viewModel) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void SettingsRow(@org.jetbrains.annotations.NotNull()
    java.lang.String title, @org.jetbrains.annotations.NotNull()
    java.lang.String subtitle) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void ThemeOption(@org.jetbrains.annotations.NotNull()
    java.lang.String title, boolean selected, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onClick) {
    }
}