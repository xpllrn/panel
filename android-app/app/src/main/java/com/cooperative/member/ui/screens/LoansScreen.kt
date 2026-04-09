package com.cooperative.member.ui.screens

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import com.cooperative.member.data.Loan
import com.cooperative.member.ui.theme.CashGreen
import com.cooperative.member.ui.theme.PanelsTheme
import com.cooperative.member.ui.theme.Red400
import com.cooperative.member.ui.viewmodel.LoansListState
import com.cooperative.member.ui.viewmodel.LoansViewModel
import com.cooperative.member.util.Fmt
import java.math.BigDecimal

@Composable
fun LoansScreen(vm: LoansViewModel, onLoanClick: (Int) -> Unit = {}) {
    val state by vm.list.collectAsState()

    when (val s = state) {
        is LoansListState.Loading -> LoadingBox()
        is LoansListState.Error -> ErrorBox(s.message) { vm.loadLoans() }
        is LoansListState.Ready -> {
            if (s.loans.isEmpty()) EmptyLoans()
            else LoansList(s.loans, onLoanClick)
        }
    }
}

@Composable
private fun EmptyLoans() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                Icons.Default.CheckCircle,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = CashGreen
            )
            Spacer(Modifier.height(16.dp))
            Text(
                "No active loans",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground
            )
            Text(
                "You're all clear!",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp)
            )
        }
    }
}

@Composable
private fun LoansList(loans: List<Loan>, onLoanClick: (Int) -> Unit) {
    val totalOutstanding = loans.sumOf {
        try { BigDecimal(it.outstanding_balance) } catch (_: Exception) { BigDecimal.ZERO }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    "Loans",
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    Fmt.rupee(totalOutstanding.toPlainString()),
                    style = MaterialTheme.typography.displayMedium,
                    color = Red400
                )
                Text(
                    "Total Outstanding",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        items(loans) { loan ->
            LoanRow(loan) { onLoanClick(loan.id) }
        }
    }
}

@Composable
private fun LoanRow(loan: Loan, onClick: () -> Unit) {
    val progress = loan.completion_percentage?.let { (it / 100.0).toFloat().coerceIn(0f, 1f) }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 5.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(42.dp),
                shape = CircleShape,
                color = Red400.copy(alpha = 0.12f)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        Icons.Default.CreditCard,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                        tint = Red400
                    )
                }
            }
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    loan.loan_type.replace("_", " ").replaceFirstChar { it.uppercase() },
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    loan.loan_number,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (progress != null) {
                    Spacer(Modifier.height(6.dp))
                    LinearProgressIndicator(
                        progress = progress,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(4.dp)
                            .clip(RoundedCornerShape(2.dp)),
                        color = CashGreen,
                        trackColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
                    )
                }
            }
            Spacer(Modifier.width(10.dp))
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    Fmt.rupee(loan.outstanding_balance),
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
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
}

@Preview(showBackground = true)
@Composable
fun LoansScreenPreview() {
    PanelsTheme {
        Surface {
            val mockLoans = listOf(
                Loan(
                    id = 1,
                    loan_type = "personal_loan",
                    loan_number = "L-12345",
                    outstanding_balance = "50000",
                    emi_amount = "2500",
                    completion_percentage = 45.0
                ),
                Loan(
                    id = 2,
                    loan_type = "vehicle_loan",
                    loan_number = "L-67890",
                    outstanding_balance = "150000",
                    emi_amount = "5500",
                    completion_percentage = 15.0
                )
            )
            LoansList(loans = mockLoans, onLoanClick = {})
        }
    }
}
