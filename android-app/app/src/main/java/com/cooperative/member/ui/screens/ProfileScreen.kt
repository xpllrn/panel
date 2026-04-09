package com.cooperative.member.ui.screens

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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cooperative.member.data.MemberProfile
import com.cooperative.member.ui.theme.Red400
import com.cooperative.member.ui.viewmodel.ProfileState
import com.cooperative.member.ui.viewmodel.ProfileViewModel
import com.cooperative.member.util.Fmt

@Composable
fun ProfileScreen(vm: ProfileViewModel) {
    val state by vm.state.collectAsState()
    val theme by vm.themeMode.collectAsState(initial = "dark")

    when (val s = state) {
        is ProfileState.Loading -> LoadingBox()
        is ProfileState.Error -> ErrorBox(s.message) { vm.loadProfile() }
        is ProfileState.Ready -> ProfileContent(s.profile, theme, vm)
    }
}

@Composable
private fun ProfileContent(p: MemberProfile, theme: String, vm: ProfileViewModel) {
    val initials = buildString {
        if (p.first_name.isNotBlank()) append(p.first_name.first().uppercase())
        if (p.last_name.isNotBlank()) append(p.last_name.first().uppercase())
        if (isEmpty()) append(p.display_name.take(2).uppercase())
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 40.dp)
    ) {
        // Avatar + name
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 28.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Surface(
                    modifier = Modifier.size(80.dp),
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(
                            initials,
                            style = MaterialTheme.typography.headlineLarge.copy(
                                fontWeight = FontWeight.Bold,
                                fontSize = 30.sp
                            ),
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                Text(
                    p.display_name,
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground
                )
                if (!p.member_id.isNullOrBlank()) {
                    Text(
                        p.member_id,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }
            }
        }

        // Personal info
        item {
            SectionHeader("Personal Info")
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(20.dp),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Column(Modifier.padding(16.dp)) {
                    if (p.email.isNotBlank()) InfoRow("Email", p.email)
                    InfoRow("Username", p.username)
                    if (p.member_type.isNotBlank()) InfoRow("Type", p.member_type.replaceFirstChar { it.uppercase() })
                    InfoRow("Status", p.status.replaceFirstChar { it.uppercase() })
                    if (!p.mobile_primary.isNullOrBlank()) InfoRow("Phone", p.mobile_primary)
                    if (!p.gender.isNullOrBlank()) InfoRow("Gender", p.gender.replaceFirstChar { it.uppercase() })
                    if (!p.date_of_birth.isNullOrBlank()) InfoRow("DOB", formatDate(p.date_of_birth))
                    if (!p.date_of_joining.isNullOrBlank()) InfoRow("Joined", formatDate(p.date_of_joining))
                    if (!p.current_city.isNullOrBlank()) InfoRow("City", p.current_city)
                    if (!p.current_state.isNullOrBlank()) InfoRow("State", p.current_state)
                }
            }
            Spacer(Modifier.height(16.dp))
        }

        // Financial info
        item {
            SectionHeader("Financial")
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(20.dp),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Column(Modifier.padding(16.dp)) {
                    InfoRow("Share Capital", Fmt.rupee(p.share_capital_amount))
                    InfoRow("Shares", p.number_of_shares.toString())
                    InfoRow("Dividend Payable", Fmt.rupee(p.dividend_payable_balance))
                }
            }
            Spacer(Modifier.height(24.dp))
        }

        // Settings section
        item {
            Row(
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.Settings,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    "Settings",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground
                )
            }

            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(20.dp),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Column(Modifier.padding(16.dp)) {
                    Text(
                        "Theme",
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ThemeChip("Light", "light", theme, Icons.Default.LightMode) { vm.setTheme("light") }
                        ThemeChip("Dark", "dark", theme, Icons.Default.DarkMode) { vm.setTheme("dark") }
                        ThemeChip("System", "system", theme, Icons.Default.Settings) { vm.setTheme("system") }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
        }

        // Sign out
        item {
            Button(
                onClick = { vm.logout() },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .height(50.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Red400.copy(alpha = 0.15f))
            ) {
                Icon(
                    Icons.AutoMirrored.Filled.Logout,
                    contentDescription = null,
                    tint = Red400,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    "Sign Out",
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold),
                    color = Red400
                )
            }

            Spacer(Modifier.height(12.dp))
            Text(
                "Cooperative Society v1.0",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp)
            )
        }
    }
}

@Composable
private fun ThemeChip(
    label: String,
    value: String,
    current: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    onClick: () -> Unit
) {
    FilterChip(
        selected = current == value,
        onClick = onClick,
        label = { Text(label) },
        leadingIcon = {
            Icon(icon, contentDescription = null, modifier = Modifier.size(16.dp))
        },
        colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
            selectedLabelColor = MaterialTheme.colorScheme.primary,
            selectedLeadingIconColor = MaterialTheme.colorScheme.primary
        )
    )
}
