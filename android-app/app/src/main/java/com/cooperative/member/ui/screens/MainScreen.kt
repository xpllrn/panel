package com.cooperative.member.ui.screens

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.NavController
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController

sealed class BottomNavItem(
    val route: String,
    val title: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector
) {
    object Dashboard : BottomNavItem("main_dashboard", "Home", Icons.Default.Home)
    object Accounts : BottomNavItem("main_accounts", "Accounts", Icons.Default.AccountBalance)
    object Loans : BottomNavItem("main_loans", "Loans", Icons.Default.CreditCard)
    object Profile : BottomNavItem("main_profile", "Profile", Icons.Default.Person)
    object Settings : BottomNavItem("main_settings", "Settings", Icons.Default.Settings)
}

@Composable
fun MainScreen(
    parentNavController: NavController,
    onLogout: () -> Unit
) {
    val navController = rememberNavController()
    val items = listOf(
        BottomNavItem.Dashboard,
        BottomNavItem.Accounts,
        BottomNavItem.Loans,
        BottomNavItem.Profile,
        BottomNavItem.Settings
    )
    
    Scaffold(
        bottomBar = {
            NavigationBar {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination
                
                items.forEach { item ->
                    NavigationBarItem(
                        icon = { Icon(item.icon, contentDescription = item.title) },
                        label = { Text(item.title) },
                        selected = currentDestination?.hierarchy?.any { it.route == item.route } == true,
                        onClick = {
                            navController.navigate(item.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { paddingValues ->
        NavHost(
            navController = navController,
            startDestination = BottomNavItem.Dashboard.route,
            modifier = Modifier.padding(paddingValues)
        ) {
            composable(BottomNavItem.Dashboard.route) {
                DashboardScreen(
                    navController = parentNavController,
                    onLogout = onLogout
                )
            }
            composable(BottomNavItem.Accounts.route) {
                AccountsScreen(navController = parentNavController)
            }
            composable(BottomNavItem.Loans.route) {
                LoansScreen(navController = parentNavController)
            }
            composable(BottomNavItem.Profile.route) {
                ProfileScreen(
                    onLogout = onLogout,
                    onNavigateToSettings = {
                        navController.navigate(BottomNavItem.Settings.route)
                    }
                )
            }
            composable(BottomNavItem.Settings.route) {
                SettingsScreen()
            }
        }
    }
}
