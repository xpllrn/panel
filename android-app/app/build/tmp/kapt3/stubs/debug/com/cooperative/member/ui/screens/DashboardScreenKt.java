package com.cooperative.member.ui.screens;

import androidx.compose.foundation.layout.*;
import androidx.compose.material.icons.Icons;
import androidx.compose.material.icons.filled.*;
import androidx.compose.material3.*;
import androidx.compose.runtime.*;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.text.font.FontWeight;
import androidx.navigation.NavController;
import com.cooperative.member.data.model.DashboardResponse;
import com.cooperative.member.ui.viewmodel.DashboardViewModel;
import com.cooperative.member.util.Resource;

@kotlin.Metadata(mv = {1, 9, 0}, k = 2, xi = 48, d1 = {"\u0000(\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\u001a2\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\u000e\b\u0002\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00010\u00072\b\b\u0002\u0010\b\u001a\u00020\tH\u0007\u001a(\u0010\n\u001a\u00020\u00012\u0006\u0010\u0004\u001a\u00020\u00052\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\u00010\u00072\b\b\u0002\u0010\f\u001a\u00020\rH\u0007\u00a8\u0006\u000e"}, d2 = {"DashboardContent", "", "dashboard", "Lcom/cooperative/member/data/model/DashboardResponse;", "navController", "Landroidx/navigation/NavController;", "onMenuClick", "Lkotlin/Function0;", "modifier", "Landroidx/compose/ui/Modifier;", "DashboardScreen", "onLogout", "viewModel", "Lcom/cooperative/member/ui/viewmodel/DashboardViewModel;", "app_debug"})
public final class DashboardScreenKt {
    
    @kotlin.OptIn(markerClass = {androidx.compose.material3.ExperimentalMaterial3Api.class})
    @androidx.compose.runtime.Composable()
    public static final void DashboardScreen(@org.jetbrains.annotations.NotNull()
    androidx.navigation.NavController navController, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onLogout, @org.jetbrains.annotations.NotNull()
    com.cooperative.member.ui.viewmodel.DashboardViewModel viewModel) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void DashboardContent(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.model.DashboardResponse dashboard, @org.jetbrains.annotations.NotNull()
    androidx.navigation.NavController navController, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onMenuClick, @org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier) {
    }
}