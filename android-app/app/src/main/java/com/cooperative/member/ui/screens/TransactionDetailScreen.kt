package com.cooperative.member.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
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
import com.cooperative.member.data.Transaction
import com.cooperative.member.ui.viewmodel.TransactionDetailState
import com.cooperative.member.ui.viewmodel.TransactionsViewModel
import com.cooperative.member.util.Fmt

@Composable
fun TransactionDetailScreen(
    transactionId: Int,
    vm: TransactionsViewModel,
    onBack: () -> Unit
) {
    LaunchedEffect(transactionId) { vm.loadDetail(transactionId) }

    val state by vm.detail.collectAsState()

    when (val s = state) {
        is TransactionDetailState.Loading -> LoadingBox()
        is TransactionDetailState.Error -> ErrorBox(s.message) { vm.loadDetail(transactionId) }
        is TransactionDetailState.Ready -> TransactionDetailContent(s.detail, onBack)
    }
}

@Composable
private fun TransactionDetailContent(tx: Transaction, onBack: () -> Unit) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(start = 4.dp, top = 8.dp, end = 12.dp, bottom = 4.dp),
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
                    "Transaction Receipt",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground
                )
            }
        }

        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 14.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    Fmt.rupee(tx.amount),
                    style = MaterialTheme.typography.displayMedium,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    tx.receipt_number.ifBlank { "Receipt unavailable" },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        item {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(20.dp),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Column(Modifier.padding(16.dp)) {
                    val typeText = tx.transaction_type_display
                        ?: tx.transaction_type.replace("_", " ").replaceFirstChar { it.uppercase() }
                    InfoRow("Type", typeText)
                    if (!tx.account_number.isNullOrBlank()) InfoRow("Account", tx.account_number)
                    InfoRow("Amount", Fmt.rupee(tx.amount))
                    if (tx.balance_after.isNotBlank()) InfoRow("Balance After", Fmt.rupee(tx.balance_after))
                    if (!tx.payment_mode.isNullOrBlank()) {
                        InfoRow("Payment Mode", tx.payment_mode.replaceFirstChar { it.uppercase() })
                    }
                    if (!tx.reference_number.isNullOrBlank()) InfoRow("Reference", tx.reference_number)
                    if (!tx.description.isNullOrBlank()) InfoRow("Description", tx.description)
                    if (!tx.remarks.isNullOrBlank()) InfoRow("Remarks", tx.remarks)
                    if (tx.created_at.isNotBlank()) InfoRow("Date", formatDate(tx.created_at))
                }
            }
            Spacer(Modifier.height(14.dp))
        }

        item {
            Text(
                "This receipt mirrors the transaction details recorded by the panel.",
                modifier = Modifier.padding(horizontal = 20.dp),
                style = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.Medium),
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
