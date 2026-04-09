package com.cooperative.member.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.foundation.background
import androidx.compose.ui.platform.LocalContext
import androidx.compose.material3.MaterialTheme
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.cooperative.member.CooperativeApp
import com.cooperative.member.ui.screens.AccountDetailScreen
import com.cooperative.member.ui.screens.LoanDetailScreen
import com.cooperative.member.ui.screens.LoginScreen
import com.cooperative.member.ui.viewmodel.AccountsViewModel
import com.cooperative.member.ui.viewmodel.LoansViewModel
import com.cooperative.member.ui.viewmodel.LoginViewModel

@Composable
fun AppNavigation() {
    val app = LocalContext.current.applicationContext as CooperativeApp
    val isLoggedIn by app.session.isLoggedIn.collectAsState(initial = false)

    val loginVm: LoginViewModel = viewModel()
    key(isLoggedIn) {
        val navController = rememberNavController()
        val start = if (isLoggedIn) "main" else "login"

        NavHost(
            navController = navController,
            startDestination = start,
            modifier = Modifier.background(MaterialTheme.colorScheme.background)
        ) {
            composable("login") {
                LoginScreen(loginVm)
            }

            composable("main") {
                MainShell(
                    onAccountClick = { id ->
                        navController.navigate("account_detail/$id")
                    },
                    onLoanClick = { id ->
                        navController.navigate("loan_detail/$id")
                    }
                )
            }

            composable(
                "account_detail/{id}",
                arguments = listOf(navArgument("id") { type = NavType.IntType })
            ) { entry ->
                val accountsVm: AccountsViewModel = viewModel()
                val id = entry.arguments?.getInt("id") ?: return@composable
                AccountDetailScreen(
                    accountId = id,
                    vm = accountsVm,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(
                "loan_detail/{id}",
                arguments = listOf(navArgument("id") { type = NavType.IntType })
            ) { entry ->
                val loansVm: LoansViewModel = viewModel()
                val id = entry.arguments?.getInt("id") ?: return@composable
                LoanDetailScreen(
                    loanId = id,
                    vm = loansVm,
                    onBack = { navController.popBackStack() }
                )
            }
        }
    }
}
