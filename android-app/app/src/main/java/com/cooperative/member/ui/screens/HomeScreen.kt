package com.cooperative.member.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.TrendingDown
import androidx.compose.material.icons.automirrored.filled.TrendingUp
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.Savings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.cooperative.member.data.AccountSummary
import com.cooperative.member.data.DashboardResponse
import com.cooperative.member.data.LoanSummary
import com.cooperative.member.data.Transaction
import com.cooperative.member.ui.theme.CashGreen
import com.cooperative.member.ui.theme.Red400
import com.cooperative.member.ui.viewmodel.HomeState
import com.cooperative.member.ui.viewmodel.HomeViewModel
import com.cooperative.member.util.Fmt

@Composable
fun HomeScreen(
    vm: HomeViewModel,
    onAccountClick: (Int) -> Unit = {},
    onLoanClick: (Int) -> Unit = {}
) {
    val state by vm.state.collectAsState()

    when (val s = state) {
        is HomeState.Loading -> LoadingBox()
        is HomeState.Error -> ErrorBox(s.message) { vm.load() }
        is HomeState.Ready -> HomeContent(s.data, onAccountClick, onLoanClick)
    }
}

@Composable
private fun HomeContent(
    d: DashboardResponse,
    onAccountClick: (Int) -> Unit,
    onLoanClick: (Int) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        // Header
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    "Hi, ${d.member.display_name.split(" ").firstOrNull() ?: "Member"}",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (!d.member.member_id.isNullOrBlank()) {
                    Text(
                        d.member.member_id,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(Modifier.height(12.dp))
                Text(
                    Fmt.rupee(d.total_balance),
                    style = MaterialTheme.typography.displayLarge,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    "Total Balance",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        // Account cards row
        if (d.accounts.isNotEmpty()) {
            item {
                SectionHeader("Accounts")
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(d.accounts) { acct ->
                        AccountCard(acct) { onAccountClick(acct.id) }
                    }
                }
                Spacer(Modifier.height(16.dp))
            }
        }

        // Loan cards row
        if (d.active_loans.isNotEmpty()) {
            item {
                SectionHeader("Active Loans")
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(d.active_loans) { loan ->
                        LoanCard(loan) { onLoanClick(loan.id) }
                    }
                }
                Spacer(Modifier.height(16.dp))
            }
        }

        // Recent transactions
        if (d.recent_transactions.isNotEmpty()) {
            item { SectionHeader("Recent Transactions") }
            items(d.recent_transactions) { tx ->
                TransactionRow(tx)
            }
        }
    }
}

// ── Reusable sub-composables ──

@Composable
fun SectionHeader(title: String, modifier: Modifier = Modifier) {
    Text(
        title,
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onBackground,
        modifier = modifier.padding(horizontal = 20.dp, vertical = 8.dp)
    )
}

@Composable
private fun AccountCard(acct: AccountSummary, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .width(160.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Column(Modifier.padding(16.dp)) {
            Surface(
                modifier = Modifier.size(36.dp),
                shape = CircleShape,
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        accountIcon(acct.account_type),
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(
                formatAccountType(acct.account_type),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                Fmt.rupee(acct.balance),
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
private fun LoanCard(loan: LoanSummary, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .width(170.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Column(Modifier.padding(16.dp)) {
            Surface(
                modifier = Modifier.size(36.dp),
                shape = CircleShape,
                color = Red400.copy(alpha = 0.15f)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        Icons.Default.CreditCard,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                        tint = Red400
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(
                loan.loan_type.replace("_", " ").replaceFirstChar { it.uppercase() },
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                Fmt.rupee(loan.outstanding_balance),
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                "EMI ${Fmt.rupee(loan.emi_amount)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
fun TransactionRow(tx: Transaction) {
    val isCredit = tx.transaction_type.lowercase().let {
        it.contains("deposit") || it.contains("credit") || it.contains("interest")
    }
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(38.dp),
                shape = CircleShape,
                color = if (isCredit) CashGreen.copy(alpha = 0.12f) else Red400.copy(alpha = 0.12f)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        if (isCredit) Icons.AutoMirrored.Filled.TrendingDown
                        else Icons.AutoMirrored.Filled.TrendingUp,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                        tint = if (isCredit) CashGreen else Red400
                    )
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    tx.description ?: tx.transaction_type.replace("_", " ").replaceFirstChar { it.uppercase() },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    tx.receipt_number.ifBlank { formatDate(tx.created_at) },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Text(
                Fmt.withSign(tx.amount, isCredit),
                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold),
                color = if (isCredit) CashGreen else Red400
            )
        }
    }
}

// ── Helpers ──

fun accountIcon(type: String): ImageVector = when (type.lowercase()) {
    "fd" -> Icons.Default.Lock
    "rd" -> Icons.Default.Repeat
    "cd" -> Icons.Default.Savings
    "od" -> Icons.Default.AccountBalance
    "share" -> Icons.Default.Share
    else -> Icons.Default.AccountBalance
}

fun formatAccountType(type: String): String = when (type.uppercase()) {
    "FD" -> "Fixed Deposit"
    "RD" -> "Recurring Deposit"
    "CD" -> "Current Deposit"
    "OD" -> "Overdraft"
    "SHARE" -> "Share"
    "SUKANYA" -> "Sukanya"
    "SUPUTRA" -> "Suputra"
    else -> type.replace("_", " ").replaceFirstChar { it.uppercase() }
}

fun formatDate(iso: String): String {
    if (iso.isBlank()) return ""
    return try {
        val parts = iso.take(10).split("-")
        "${parts[2]}/${parts[1]}/${parts[0]}"
    } catch (_: Exception) {
        iso.take(10)
    }
}

@Composable
fun LoadingBox() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
    }
}

@Composable
fun ErrorBox(message: String, onRetry: () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                message,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.error
            )
            Spacer(Modifier.height(12.dp))
            TextButton(onClick = onRetry) {
                Text("Retry", color = MaterialTheme.colorScheme.primary)
            }
        }
    }
}
