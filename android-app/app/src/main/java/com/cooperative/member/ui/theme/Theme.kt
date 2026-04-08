package com.cooperative.member.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import com.cooperative.member.data.preferences.ThemeMode

private val DarkColorScheme = darkColorScheme(
    primary = DarkPrimary,
    onPrimary = Color.White,
    primaryContainer = DarkSurfaceVariant,
    onPrimaryContainer = Color.White,
    secondary = DarkGreen,
    onSecondary = Color.White,
    background = DarkBackground,
    onBackground = Color.White,
    surface = DarkSurface,
    onSurface = Color.White,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = Color(0xFFB0B0B0),
    error = DarkRed,
    onError = Color.White,
    errorContainer = Color(0xFF5C1A1A),
    onErrorContainer = Color(0xFFFFB4AB)
)

private val AmoledColorScheme = darkColorScheme(
    primary = AmoledPrimary,
    onPrimary = Color.White,
    primaryContainer = AmoledSurfaceVariant,
    onPrimaryContainer = Color.White,
    secondary = AmoledGreen,
    onSecondary = Color.White,
    background = AmoledBackground,
    onBackground = Color.White,
    surface = AmoledSurface,
    onSurface = Color.White,
    surfaceVariant = AmoledSurfaceVariant,
    onSurfaceVariant = Color(0xFFB0B0B0),
    error = AmoledRed,
    onError = Color.White,
    errorContainer = Color(0xFF3A0000),
    onErrorContainer = Color(0xFFFFB4AB)
)

private val LightColorScheme = lightColorScheme(
    primary = BankBlue,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE3F2FD),
    onPrimaryContainer = BankBlueDark,
    secondary = BankGreen,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE8F5E9),
    onSecondaryContainer = Color(0xFF1B5E20),
    background = BankLightGray,
    onBackground = Color(0xFF1C1B1F),
    surface = BankWhite,
    onSurface = Color(0xFF1C1B1F),
    surfaceVariant = Color(0xFFF8F9FA),
    onSurfaceVariant = BankGray,
    error = BankRed,
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    outline = BankDivider
)

@Composable
fun CooperativeMemberTheme(
    themeMode: ThemeMode = ThemeMode.SYSTEM,
    content: @Composable () -> Unit
) {
    val systemInDarkTheme = isSystemInDarkTheme()
    
    val colorScheme = when (themeMode) {
        ThemeMode.LIGHT -> LightColorScheme
        ThemeMode.DARK -> DarkColorScheme
        ThemeMode.AMOLED -> AmoledColorScheme
        ThemeMode.SYSTEM -> if (systemInDarkTheme) DarkColorScheme else LightColorScheme
    }
    
    val isDark = when (themeMode) {
        ThemeMode.LIGHT -> false
        ThemeMode.DARK, ThemeMode.AMOLED -> true
        ThemeMode.SYSTEM -> systemInDarkTheme
    }
    
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !isDark
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
