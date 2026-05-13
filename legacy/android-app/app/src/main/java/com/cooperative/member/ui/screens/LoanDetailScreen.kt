package com.panels.danc.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.panels.danc.data.LoanDetailResponse
import com.panels.danc.data.LoanRepayment
import com.panels.danc.ui.theme.CashGreen
import com.panels.danc.ui.theme.Red400
import com.panels.danc.ui.viewmodel.LoanDetailState
import com.panels.danc.ui.viewmodel.LoansViewModel
import com.panels.danc.util.Fmt

@Composable
fun LoanDetailScreen(
    loanId: Int,
    vm: LoansViewModel,
    onBack: () -> Unit
) {
    LaunchedEffect(loanId) { vm.loadDetail(loanId) }

    val state by vm.detail.collectAsState()

    when (val s = state) {
        is LoanDetailState.Loading -> LoadingBox()
        is LoanDetailState.Error -> ErrorBox(s.message) { vm.loadDetail(loanId) }
        is LoanDetailState.Ready -> LoanContent(s.detail, onBack)
    }
}

@Composable
private fun LoanContent(d: LoanDetailResponse, onBack: () -> Unit) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        // Header
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
                    d.loan_type.replace("_", " ").replaceFirstChar { it.uppercase() } + " Loan",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground
                )
            }
        }

        // Outstanding hero
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    Fmt.rupee(d.outstanding_balance),
                    style = MaterialTheme.typography.displayMedium,
                    color = Red400
                )
                Text(
                    "Outstanding Balance",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        // EMI + Interest cards
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                HighlightCard("EMI", Fmt.rupee(d.emi_amount), CashGreen, Modifier.weight(1f))
                HighlightCard("Interest", "${d.interest_rate}%", MaterialTheme.colorScheme.onBackground, Modifier.weight(1f))
            }
            Spacer(Modifier.height(12.dp))
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
                    InfoRow("Loan Number", d.loan_number)
                    InfoRow("Principal", Fmt.rupee(d.principal_amount))
                    InfoRow("Tenure", "${d.tenure_months} months")
                    InfoRow("Status", (d.status_display ?: d.status).replaceFirstChar { it.uppercase() })
                    if (!d.interest_type.isNullOrBlank()) InfoRow("Interest Type", d.interest_type)
                    if (!d.application_date.isNullOrBlank()) InfoRow("Applied", formatDate(d.application_date))
                    if (!d.approval_date.isNullOrBlank()) InfoRow("Approved", formatDate(d.approval_date))
                    if (!d.disbursement_date.isNullOrBlank()) InfoRow("Disbursed", formatDate(d.disbursement_date))
                    if (!d.first_emi_date.isNullOrBlank()) InfoRow("First EMI", formatDate(d.first_emi_date))
                    if (!d.processing_fee.isNullOrBlank()) InfoRow("Processing Fee", Fmt.rupee(d.processing_fee))
                    if (!d.total_payable.isNullOrBlank()) InfoRow("Total Payable", Fmt.rupee(d.total_payable))
                    if (!d.total_paid.isNullOrBlank()) InfoRow("Total Paid", Fmt.rupee(d.total_paid))
                    if (d.emis_paid != null && d.total_emis != null) {
                        InfoRow("EMIs Paid", "${d.emis_paid} / ${d.total_emis}")
                    }
                    if (!d.purpose.isNullOrBlank()) InfoRow("Purpose", d.purpose)
                }
            }
            Spacer(Modifier.height(16.dp))
        }

        // Repayment schedule
        if (d.repayments.isNotEmpty()) {
            item { SectionHeader("Repayment Schedule") }
            items(d.repayments) { rep ->
                RepaymentRow(rep)
            }
        }
    }
}

@Composable
private fun HighlightCard(
    label: String,
    value: String,
    valueColor: androidx.compose.ui.graphics.Color,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(4.dp))
            Text(
                value,
                style = MaterialTheme.typography.headlineSmall,
                color = valueColor
            )
        }
    }
}

@Composable
private fun RepaymentRow(rep: LoanRepayment) {
    val isPaid = rep.payment_status?.lowercase()?.let {
        it == "paid" || it == "completed"
    } ?: false

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
            Column(Modifier.weight(1f)) {
                Text(
                    "Installment #${rep.installment_number}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    "Due: ${formatDate(rep.due_date)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (!rep.paid_date.isNullOrBlank()) {
                    Text(
                        "Paid: ${formatDate(rep.paid_date)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = CashGreen
                    )
                }
            }
            Spacer(Modifier.width(8.dp))
            Column(horizontalAlignment = Alignment.End) {
                val amount = rep.amount_due ?: rep.amount_paid ?: "0"
                Text(
                    Fmt.rupee(amount),
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold),
                    color = if (isPaid) CashGreen else MaterialTheme.colorScheme.onBackground
                )
                Text(
                    if (isPaid) "Paid" else (rep.payment_status ?: "Pending").replaceFirstChar { it.uppercase() },
                    style = MaterialTheme.typography.labelSmall,
                    color = if (isPaid) CashGreen else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
