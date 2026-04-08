package com.cooperative.member.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.cooperative.member.data.model.LoanDetail
import com.cooperative.member.ui.viewmodel.LoanViewModel
import com.cooperative.member.util.Resource

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoanDetailScreen(
    navController: NavController,
    loanId: Int,
    viewModel: LoanViewModel = hiltViewModel()
) {
    val loanDetailState by viewModel.loanDetailState.collectAsState()
    
    LaunchedEffect(loanId) {
        viewModel.loadLoanDetail(loanId)
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Loan Details") },
                navigationIcon = {
                    IconButton(onClick = { navController.navigateUp() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    navigationIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        }
    ) { paddingValues ->
        when (val state = loanDetailState) {
            is Resource.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentAlignment = Alignment.Center
                ) {
                    Text("Loading loan details...")
                }
            }
            is Resource.Success -> {
                LoanDetailContent(
                    loanDetail = state.data!!,
                    modifier = Modifier.padding(paddingValues)
                )
            }
            is Resource.Error -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = state.message ?: "Error loading loan",
                            color = MaterialTheme.colorScheme.error
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = { viewModel.loadLoanDetail(loanId) }) {
                            Text("Retry")
                        }
                    }
                }
            }
            null -> {}
        }
    }
}

@Composable
fun LoanDetailContent(
    loanDetail: LoanDetail,
    modifier: Modifier = Modifier
) {
    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Loan Info Card
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = loanDetail.loan.loan_type.uppercase(),
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = loanDetail.loan.loan_number,
                        style = MaterialTheme.typography.bodyLarge
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column {
                            Text(
                                text = "Outstanding",
                                style = MaterialTheme.typography.bodySmall
                            )
                            Text(
                                text = "₹${loanDetail.loan.outstanding_balance}",
                                style = MaterialTheme.typography.headlineMedium,
                                color = MaterialTheme.colorScheme.error,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(
                                text = "EMI Amount",
                                style = MaterialTheme.typography.bodySmall
                            )
                            Text(
                                text = "₹${loanDetail.loan.emi_amount}",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    Divider()
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Principal:", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "₹${loanDetail.loan.principal_amount}",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Interest Rate:", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "${loanDetail.loan.interest_rate}%",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Tenure:", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "${loanDetail.loan.tenure_months} months",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    
                    if (loanDetail.loan.disbursement_date != null) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Disbursement:", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                loanDetail.loan.disbursement_date,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Status:", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            loanDetail.loan.status.uppercase(),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }
        }
        
        // Repayment Schedule
        if (loanDetail.repayment_schedule?.isNotEmpty() == true) {
            item {
                Text(
                    text = "Repayment Schedule",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(vertical = 8.dp)
                )
            }
            
            items(loanDetail.repayment_schedule ?: emptyList()) { emi ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = when (emi.status) {
                            "paid" -> MaterialTheme.colorScheme.primaryContainer
                            "overdue" -> MaterialTheme.colorScheme.errorContainer
                            else -> MaterialTheme.colorScheme.surfaceVariant
                        }
                    )
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "EMI #${emi.installment_number}",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = emi.status.uppercase(),
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = when (emi.status) {
                                    "paid" -> MaterialTheme.colorScheme.primary
                                    "overdue" -> MaterialTheme.colorScheme.error
                                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                                }
                            )
                        }
                        
                        Spacer(modifier = Modifier.height(8.dp))
                        
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Due Date:", style = MaterialTheme.typography.bodySmall)
                            Text(
                                emi.due_date,
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("EMI Amount:", style = MaterialTheme.typography.bodySmall)
                            Text(
                                "₹${emi.total_emi}",
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Principal:", style = MaterialTheme.typography.bodySmall)
                            Text(
                                "₹${emi.principal_component}",
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                        
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Interest:", style = MaterialTheme.typography.bodySmall)
                            Text(
                                "₹${emi.interest_component}",
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                        
                        if (emi.payment_date != null) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Divider()
                            Spacer(modifier = Modifier.height(4.dp))
                            
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Paid On:", style = MaterialTheme.typography.bodySmall)
                                Text(
                                    emi.payment_date,
                                    style = MaterialTheme.typography.bodySmall,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                            
                            if (emi.amount_paid != null) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Amount Paid:", style = MaterialTheme.typography.bodySmall)
                                    Text(
                                        "₹${emi.amount_paid}",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                }
                            }
                            
                            if (emi.late_penalty != null && emi.late_penalty != "0.00") {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Late Penalty:", style = MaterialTheme.typography.bodySmall)
                                    Text(
                                        "₹${emi.late_penalty}",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.error
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
