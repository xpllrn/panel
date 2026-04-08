package com.cooperative.member.data.preferences;

import android.content.Context;
import androidx.datastore.core.DataStore;
import androidx.datastore.preferences.core.Preferences;
import dagger.hilt.android.qualifiers.ApplicationContext;
import kotlinx.coroutines.flow.Flow;
import javax.inject.Inject;
import javax.inject.Singleton;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\f\n\u0002\u0018\u0002\n\u0002\u0010\u0010\n\u0002\b\u0006\b\u0086\u0081\u0002\u0018\u00002\b\u0012\u0004\u0012\u00020\u00000\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002j\u0002\b\u0003j\u0002\b\u0004j\u0002\b\u0005j\u0002\b\u0006\u00a8\u0006\u0007"}, d2 = {"Lcom/cooperative/member/data/preferences/ThemeMode;", "", "(Ljava/lang/String;I)V", "LIGHT", "DARK", "AMOLED", "SYSTEM", "app_debug"})
public enum ThemeMode {
    /*public static final*/ LIGHT /* = new LIGHT() */,
    /*public static final*/ DARK /* = new DARK() */,
    /*public static final*/ AMOLED /* = new AMOLED() */,
    /*public static final*/ SYSTEM /* = new SYSTEM() */;
    
    ThemeMode() {
    }
    
    @org.jetbrains.annotations.NotNull()
    public static kotlin.enums.EnumEntries<com.cooperative.member.data.preferences.ThemeMode> getEntries() {
        return null;
    }
}