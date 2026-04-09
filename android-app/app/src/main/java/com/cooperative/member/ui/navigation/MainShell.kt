package com.cooperative.member.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.outlined.AccountBalance
import androidx.compose.material.icons.outlined.CreditCard
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.cooperative.member.ui.screens.AccountsScreen
import com.cooperative.member.ui.screens.AboutScreen
import com.cooperative.member.ui.screens.EditProfileScreen
import com.cooperative.member.ui.screens.HomeScreen
import com.cooperative.member.ui.screens.LoadingBox
import com.cooperative.member.ui.screens.LoansScreen
import com.cooperative.member.ui.screens.ProfileScreen
import com.cooperative.member.ui.viewmodel.ProfileState
import com.cooperative.member.ui.viewmodel.AccountsViewModel
import com.cooperative.member.ui.viewmodel.HomeViewModel
import com.cooperative.member.ui.viewmodel.LoansViewModel
import com.cooperative.member.ui.viewmodel.ProfileViewModel

private data class Tab(
    val route: String,
    val label: String,
    val filledIcon: ImageVector,
    val outlinedIcon: ImageVector
)

private val tabs = listOf(
    Tab("home", "Home", Icons.Filled.Home, Icons.Outlined.Home),
    Tab("accounts", "Accounts", Icons.Filled.AccountBalance, Icons.Outlined.AccountBalance),
    Tab("loans", "Loans", Icons.Filled.CreditCard, Icons.Outlined.CreditCard),
    Tab("profile", "Profile", Icons.Filled.Person, Icons.Outlined.Person)
)

@Composable
fun MainShell(
    onAccountClick: (Int) -> Unit,
    onLoanClick: (Int) -> Unit
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val homeVm: HomeViewModel = viewModel()
    val accountsVm: AccountsViewModel = viewModel()
    val loansVm: LoansViewModel = viewModel()
    val profileVm: ProfileViewModel = viewModel()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surface,
                tonalElevation = 0.dp
            ) {
                tabs.forEach { tab ->
                    val selected = currentDestination?.hierarchy?.any {
                        when (tab.route) {
                            "profile" -> it.route in setOf("profile", "profile_edit", "about")
                            else -> it.route == tab.route
                        }
                    } == true
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            Icon(
                                if (selected) tab.filledIcon else tab.outlinedIcon,
                                contentDescription = tab.label
                            )
                        },
                        label = { Text(tab.label, style = MaterialTheme.typography.labelSmall) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.primary,
                            selectedTextColor = MaterialTheme.colorScheme.primary,
                            unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            indicatorColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)
                        )
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = "home",
            modifier = Modifier.padding(innerPadding)
        ) {
            composable("home") { HomeScreen(homeVm, onAccountClick, onLoanClick) }
            composable("accounts") { AccountsScreen(accountsVm, onAccountClick) }
            composable("loans") { LoansScreen(loansVm, onLoanClick) }
            composable("profile") {
                ProfileScreen(
                    vm = profileVm,
                    onAboutClick = { navController.navigate("about") },
                    onEditProfileClick = { navController.navigate("profile_edit") }
                )
            }
            composable("profile_edit") {
                val current = profileVm.state.value
                if (current is ProfileState.Ready) {
                    EditProfileScreen(
                        profile = current.profile,
                        vm = profileVm,
                        onBack = { navController.popBackStack() }
                    )
                } else {
                    LoadingBox()
                }
            }
            composable("about") {
                AboutScreen(onBack = { navController.popBackStack() })
            }
        }
    }
}
