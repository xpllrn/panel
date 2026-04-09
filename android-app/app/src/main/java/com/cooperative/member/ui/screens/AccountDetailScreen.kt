package com.cooperative.member.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.cooperative.member.data.AccountDetailResponse
import com.cooperative.member.ui.viewmodel.AccountDetailState
import com.cooperative.member.ui.viewmodel.AccountsViewModel
import com.cooperative.member.util.Fmt

@Composable
fun AccountDetailScreen(
    accountId: Int,
    vm: AccountsViewModel,
    onBack: () -> Unit
) {
    LaunchedEffect(accountId) { vm.loadDetail(accountId) }

    val state by vm.detail.collectAsState()

    when (val s = state) {
        is AccountDetailState.Loading -> LoadingBox()
        is AccountDetailState.Error -> ErrorBox(s.message) { vm.loadDetail(accountId) }
        is AccountDetailState.Ready -> DetailContent(s.detail, onBack)
    }
}

@Composable
private fun DetailContent(d: AccountDetailResponse, onBack: () -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        // Header with back
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 4.dp, top = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "Back",
                        tint = MaterialTheme.colorScheme.onBackground
                    )
                }
                Text(
                    formatAccountType(d.account_type),
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground
                )
            }
        }

        // Balance hero
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    Fmt.rupee(d.balance),
                    style = MaterialTheme.typography.displayMedium,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    d.account_number,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        // Info card
        item {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(20.dp),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Column(Modifier.padding(16.dp)) {
                    InfoRow("Status", (d.status_display ?: d.status).replaceFirstChar { it.uppercase() })
                    if (!d.interest_rate.isNullOrBlank()) InfoRow("Interest Rate", "${d.interest_rate}%")
                    if (!d.principal_amount.isNullOrBlank()) InfoRow("Principal", Fmt.rupee(d.principal_amount))
                    if (d.tenure_months != null) InfoRow("Tenure", "${d.tenure_months} months")
                    if (!d.opening_date.isNullOrBlank()) InfoRow("Opened", formatDate(d.opening_date))
                    if (!d.maturity_date.isNullOrBlank()) InfoRow("Matures", formatDate(d.maturity_date))
                    if (!d.accrued_interest.isNullOrBlank()) InfoRow("Accrued Interest", Fmt.rupee(d.accrued_interest))
                    if (!d.nominee_name.isNullOrBlank()) InfoRow("Nominee", d.nominee_name)
                }
            }
            Spacer(Modifier.height(16.dp))
        }

        // Transactions
        if (d.transactions.isNotEmpty()) {
            item { SectionHeader("Transactions") }
            items(d.transactions) { tx -> TransactionRow(tx) }
        }
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f)
        )
        Text(
            value,
            style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
            color = MaterialTheme.colorScheme.onBackground
        )
    }
}
