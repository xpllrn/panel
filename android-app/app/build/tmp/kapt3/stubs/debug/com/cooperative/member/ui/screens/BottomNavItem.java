package com.cooperative.member.ui.screens;

import androidx.compose.material.icons.Icons;
import androidx.compose.material.icons.filled.*;
import androidx.compose.material3.*;
import androidx.compose.runtime.*;
import androidx.compose.ui.Modifier;
import androidx.navigation.NavController;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u00000\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u000b\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\b7\u0018\u00002\u00020\u0001:\u0005\r\u000e\u000f\u0010\u0011B\u001f\b\u0004\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0006\u00a2\u0006\u0002\u0010\u0007R\u0011\u0010\u0005\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\b\u0010\tR\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0011\u0010\u0004\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\f\u0010\u000b\u0082\u0001\u0005\u0012\u0013\u0014\u0015\u0016\u00a8\u0006\u0017"}, d2 = {"Lcom/cooperative/member/ui/screens/BottomNavItem;", "", "route", "", "title", "icon", "Landroidx/compose/ui/graphics/vector/ImageVector;", "(Ljava/lang/String;Ljava/lang/String;Landroidx/compose/ui/graphics/vector/ImageVector;)V", "getIcon", "()Landroidx/compose/ui/graphics/vector/ImageVector;", "getRoute", "()Ljava/lang/String;", "getTitle", "Accounts", "Dashboard", "Loans", "Profile", "Settings", "Lcom/cooperative/member/ui/screens/BottomNavItem$Accounts;", "Lcom/cooperative/member/ui/screens/BottomNavItem$Dashboard;", "Lcom/cooperative/member/ui/screens/BottomNavItem$Loans;", "Lcom/cooperative/member/ui/screens/BottomNavItem$Profile;", "Lcom/cooperative/member/ui/screens/BottomNavItem$Settings;", "app_debug"})
public abstract class BottomNavItem {
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String route = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String title = null;
    @org.jetbrains.annotations.NotNull()
    private final androidx.compose.ui.graphics.vector.ImageVector icon = null;
    
    private BottomNavItem(java.lang.String route, java.lang.String title, androidx.compose.ui.graphics.vector.ImageVector icon) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getRoute() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getTitle() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final androidx.compose.ui.graphics.vector.ImageVector getIcon() {
        return null;
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\f\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u00c7\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002\u00a8\u0006\u0003"}, d2 = {"Lcom/cooperative/member/ui/screens/BottomNavItem$Accounts;", "Lcom/cooperative/member/ui/screens/BottomNavItem;", "()V", "app_debug"})
    public static final class Accounts extends com.cooperative.member.ui.screens.BottomNavItem {
        @org.jetbrains.annotations.NotNull()
        public static final com.cooperative.member.ui.screens.BottomNavItem.Accounts INSTANCE = null;
        
        private Accounts() {
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\f\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u00c7\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002\u00a8\u0006\u0003"}, d2 = {"Lcom/cooperative/member/ui/screens/BottomNavItem$Dashboard;", "Lcom/cooperative/member/ui/screens/BottomNavItem;", "()V", "app_debug"})
    public static final class Dashboard extends com.cooperative.member.ui.screens.BottomNavItem {
        @org.jetbrains.annotations.NotNull()
        public static final com.cooperative.member.ui.screens.BottomNavItem.Dashboard INSTANCE = null;
        
        private Dashboard() {
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\f\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u00c7\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002\u00a8\u0006\u0003"}, d2 = {"Lcom/cooperative/member/ui/screens/BottomNavItem$Loans;", "Lcom/cooperative/member/ui/screens/BottomNavItem;", "()V", "app_debug"})
    public static final class Loans extends com.cooperative.member.ui.screens.BottomNavItem {
        @org.jetbrains.annotations.NotNull()
        public static final com.cooperative.member.ui.screens.BottomNavItem.Loans INSTANCE = null;
        
        private Loans() {
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\f\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u00c7\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002\u00a8\u0006\u0003"}, d2 = {"Lcom/cooperative/member/ui/screens/BottomNavItem$Profile;", "Lcom/cooperative/member/ui/screens/BottomNavItem;", "()V", "app_debug"})
    public static final class Profile extends com.cooperative.member.ui.screens.BottomNavItem {
        @org.jetbrains.annotations.NotNull()
        public static final com.cooperative.member.ui.screens.BottomNavItem.Profile INSTANCE = null;
        
        private Profile() {
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\f\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u00c7\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002\u00a8\u0006\u0003"}, d2 = {"Lcom/cooperative/member/ui/screens/BottomNavItem$Settings;", "Lcom/cooperative/member/ui/screens/BottomNavItem;", "()V", "app_debug"})
    public static final class Settings extends com.cooperative.member.ui.screens.BottomNavItem {
        @org.jetbrains.annotations.NotNull()
        public static final com.cooperative.member.ui.screens.BottomNavItem.Settings INSTANCE = null;
        
        private Settings() {
        }
    }
}