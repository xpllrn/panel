package com.cooperative.member.data.preferences;

import android.content.Context;
import androidx.datastore.core.DataStore;
import androidx.datastore.preferences.core.Preferences;
import dagger.hilt.android.qualifiers.ApplicationContext;
import kotlinx.coroutines.flow.Flow;
import javax.inject.Inject;
import javax.inject.Singleton;

@javax.inject.Singleton()
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u00000\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0003\b\u0007\u0018\u00002\u00020\u0001B\u0011\b\u0007\u0012\b\b\u0001\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J\u0016\u0010\r\u001a\u00020\u000e2\u0006\u0010\u000f\u001a\u00020\nH\u0086@\u00a2\u0006\u0002\u0010\u0010R\u0014\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0017\u0010\b\u001a\b\u0012\u0004\u0012\u00020\n0\t\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\f\u00a8\u0006\u0011"}, d2 = {"Lcom/cooperative/member/data/preferences/ThemeManager;", "", "context", "Landroid/content/Context;", "(Landroid/content/Context;)V", "THEME_MODE_KEY", "Landroidx/datastore/preferences/core/Preferences$Key;", "", "themeMode", "Lkotlinx/coroutines/flow/Flow;", "Lcom/cooperative/member/data/preferences/ThemeMode;", "getThemeMode", "()Lkotlinx/coroutines/flow/Flow;", "setThemeMode", "", "mode", "(Lcom/cooperative/member/data/preferences/ThemeMode;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "app_debug"})
public final class ThemeManager {
    @org.jetbrains.annotations.NotNull()
    private final android.content.Context context = null;
    @org.jetbrains.annotations.NotNull()
    private final androidx.datastore.preferences.core.Preferences.Key<java.lang.String> THEME_MODE_KEY = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.Flow<com.cooperative.member.data.preferences.ThemeMode> themeMode = null;
    
    @javax.inject.Inject()
    public ThemeManager(@dagger.hilt.android.qualifiers.ApplicationContext()
    @org.jetbrains.annotations.NotNull()
    android.content.Context context) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.Flow<com.cooperative.member.data.preferences.ThemeMode> getThemeMode() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object setThemeMode(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.preferences.ThemeMode mode, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
}