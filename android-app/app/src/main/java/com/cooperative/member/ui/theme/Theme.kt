package com.cooperative.member.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat

private val LightColors = lightColorScheme(
    primary = CashGreen,
    onPrimary = White,
    primaryContainer = CashGreenLight,
    onPrimaryContainer = CashGreenDark,
    secondary = Gray700,
    onSecondary = White,
    background = White,
    onBackground = Gray900,
    surface = White,
    onSurface = Gray900,
    surfaceVariant = Gray100,
    onSurfaceVariant = Gray500,
    error = Red500,
    onError = White,
    errorContainer = Color(0xFFFEE2E2),
    onErrorContainer = Red600,
    outline = Gray300,
    outlineVariant = Gray200
)

private val DarkColors = darkColorScheme(
    primary = DarkGreen,
    onPrimary = Black,
    primaryContainer = Color(0xFF003D0F),
    onPrimaryContainer = DarkGreen,
    secondary = Gray400,
    onSecondary = Black,
    background = DarkBg,
    onBackground = Gray100,
    surface = DarkSurface,
    onSurface = Gray100,
    surfaceVariant = DarkCard,
    onSurfaceVariant = Gray400,
    error = Red400,
    onError = Black,
    errorContainer = Color(0xFF3B1111),
    onErrorContainer = Red400,
    outline = Gray600,
    outlineVariant = Gray700
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp)
)

@Composable
fun CooperativeTheme(
    themeMode: String = "dark",
    content: @Composable () -> Unit
) {
    val systemDark = isSystemInDarkTheme()
    val useDark = when (themeMode) {
        "light" -> false
        "dark" -> true
        else -> systemDark
    }
    val colors = if (useDark) DarkColors else LightColors

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colors.background.toArgb()
            window.navigationBarColor = colors.background.toArgb()
            val ctrl = WindowCompat.getInsetsController(window, view)
            ctrl.isAppearanceLightStatusBars = !useDark
            ctrl.isAppearanceLightNavigationBars = !useDark
        }
    }

    MaterialTheme(
        colorScheme = colors,
        typography = AppTypography,
        shapes = AppShapes,
        content = content
    )
}
