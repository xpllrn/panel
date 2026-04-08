package com.cooperative.member.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.cooperative.member.ui.screens.*
import com.cooperative.member.ui.viewmodel.LoginViewModel

@Composable
fun AppNavigation() {
    val navController = rememberNavController()
    val loginViewModel: LoginViewModel = hiltViewModel()
    val isLoggedIn by loginViewModel.isLoggedIn.collectAsState()
    
    NavHost(
        navController = navController,
        startDestination = if (isLoggedIn) "main" else "login"
    ) {
        composable("login") {
            LoginScreen(
                navController = navController,
                viewModel = loginViewModel
            )
        }
        
        composable("main") {
            MainScreen(
                parentNavController = navController,
                onLogout = {
                    loginViewModel.logout()
                    navController.navigate("login") {
                        popUpTo("main") { inclusive = true }
                    }
                }
            )
        }
        
        composable(
            route = "account_detail/{accountId}",
            arguments = listOf(navArgument("accountId") { type = NavType.IntType })
        ) { backStackEntry ->
            val accountId = backStackEntry.arguments?.getInt("accountId") ?: 0
            AccountDetailScreen(
                navController = navController,
                accountId = accountId
            )
        }
        
        composable(
            route = "loan_detail/{loanId}",
            arguments = listOf(navArgument("loanId") { type = NavType.IntType })
        ) { backStackEntry ->
            val loanId = backStackEntry.arguments?.getInt("loanId") ?: 0
            LoanDetailScreen(
                navController = navController,
                loanId = loanId
            )
        }
        
        composable("transactions") {
            TransactionsScreen(navController = navController)
        }
        
        composable("settings") {
            SettingsScreen()
        }
    }
}
