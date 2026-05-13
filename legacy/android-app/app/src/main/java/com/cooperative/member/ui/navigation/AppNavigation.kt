package com.panels.danc.ui.navigation

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.foundation.background
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.compose.material3.MaterialTheme
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.panels.danc.CooperativeApp
import com.panels.danc.ui.screens.AccountDetailScreen
import com.panels.danc.ui.screens.LoanDetailScreen
import com.panels.danc.ui.screens.LoginScreen
import com.panels.danc.ui.screens.TransactionDetailScreen
import com.panels.danc.ui.viewmodel.AccountsViewModel
import com.panels.danc.ui.viewmodel.LoansViewModel
import com.panels.danc.ui.viewmodel.LoginViewModel
import com.panels.danc.ui.viewmodel.TransactionsViewModel

@Composable
fun AppNavigation() {
    val context = LocalContext.current
    val app = context.applicationContext as CooperativeApp
    val isLoggedIn by app.session.isLoggedIn.collectAsState(initial = false)

    val notifyPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* optional: re-sync after grant */ }

    LaunchedEffect(isLoggedIn) {
        if (!isLoggedIn) return@LaunchedEffect
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                notifyPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
        app.repository.syncFcmTokenToServer()
    }

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
                    },
                    onTransactionClick = { id ->
                        navController.navigate("transaction_detail/$id")
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

            composable(
                "transaction_detail/{id}",
                arguments = listOf(navArgument("id") { type = NavType.IntType })
            ) { entry ->
                val txVm: TransactionsViewModel = viewModel()
                val id = entry.arguments?.getInt("id") ?: return@composable
                TransactionDetailScreen(
                    transactionId = id,
                    vm = txVm,
                    onBack = { navController.popBackStack() }
                )
            }
        }
    }
}
