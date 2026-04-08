package com.cooperative.member.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.cooperative.member.data.model.DashboardResponse
import com.cooperative.member.ui.viewmodel.DashboardViewModel
import com.cooperative.member.util.Resource

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    navController: NavController,
    onLogout: () -> Unit,
    viewModel: DashboardViewModel = hiltViewModel()
) {
    val dashboardState by viewModel.dashboardState.collectAsState()
    var showMenu by remember { mutableStateOf(false) }
    
    Box(modifier = Modifier.fillMaxSize()) {
        when (val state = dashboardState) {
            is Resource.Loading -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = null,
                            modifier = Modifier.size(48.dp),
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Text(
                            text = "Loading...",
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                }
            }
            is Resource.Success -> {
                DashboardContent(
                    dashboard = state.data!!,
                    navController = navController,
                    onMenuClick = { showMenu = true },
                    modifier = Modifier.fillMaxSize()
                )
            }
            is Resource.Error -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ErrorOutline,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp),
                            tint = MaterialTheme.colorScheme.error
                        )
                        Text(
                            text = state.message ?: "Error loading dashboard",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyLarge
                        )
                        Button(onClick = { viewModel.loadDashboard() }) {
                            Icon(Icons.Default.Refresh, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Retry")
                        }
                    }
                }
            }
            null -> {}
        }
        
        // Minimal menu
        DropdownMenu(
            expanded = showMenu,
            onDismissRequest = { showMenu = false }
        ) {
            DropdownMenuItem(
                text = { Text("Refresh") },
                onClick = {
                    viewModel.loadDashboard()
                    showMenu = false
                },
                leadingIcon = { Icon(Icons.Default.Refresh, null) }
            )
            DropdownMenuItem(
                text = { Text("Logout") },
                onClick = {
                    showMenu = false
                    onLogout()
                },
                leadingIcon = { Icon(Icons.AutoMirrored.Filled.ExitToApp, null) }
            )
        }
    }
}

@Composable
fun DashboardContent(
    dashboard: DashboardResponse,
    navController: NavController,
    onMenuClick: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        // Minimal header with name and menu
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Hello,",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = dashboard.member.display_name.split(" ").firstOrNull() ?: dashboard.member.display_name,
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold
                    )
                }
                IconButton(onClick = onMenuClick) {
                    Icon(
                        Icons.Default.MoreVert,
                        contentDescription = "Menu",
                        tint = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
        
        // Big balance card - minimal and clean
        item {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { navController.navigate("transactions") },
                shape = MaterialTheme.shapes.extraLarge,
                color = MaterialTheme.colorScheme.primary,
                tonalElevation = 0.dp
            ) {
                Column(
                    modifier = Modifier.padding(28.dp)
                ) {
                    Text(
                        text = "Total Balance",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "₹${dashboard.total_balance}",
                        style = MaterialTheme.typography.displayMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "${dashboard.total_accounts} accounts",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.7f)
                    )
                }
            }
        }
        
        // Loans summary card - if any loans exist
        if (dashboard.total_active_loans > 0) {
            item {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.extraLarge,
                    color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f),
                    tonalElevation = 0.dp
                ) {
                    Column(
                        modifier = Modifier.padding(28.dp)
                    ) {
                        Text(
                            text = "Outstanding Loans",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "₹${dashboard.total_outstanding}",
                            style = MaterialTheme.typography.displayMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.error
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "${dashboard.total_active_loans} active loans",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
        
        // Recent transactions - minimal
        if (dashboard.recent_transactions.isNotEmpty()) {
            item {
                Text(
                    text = "Recent",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 8.dp)
                )
            }
            
            items(dashboard.recent_transactions.take(5)) { transaction ->
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.large,
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
                    tonalElevation = 0.dp
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = transaction.transaction_type.replaceFirstChar { it.uppercase() },
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Medium
                            )
                            Text(
                                text = transaction.created_at.substringBefore("T"),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Text(
                            text = if (transaction.transaction_type == "credit") "+₹${transaction.amount}" else "-₹${transaction.amount}",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = if (transaction.transaction_type == "credit") 
                                MaterialTheme.colorScheme.primary 
                            else 
                                MaterialTheme.colorScheme.error
                        )
                    }
                }
            }
        }
        
        // Bottom spacing
        item {
            Spacer(modifier = Modifier.height(80.dp))
        }
    }
}
