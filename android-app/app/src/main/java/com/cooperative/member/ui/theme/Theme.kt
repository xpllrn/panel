package com.panels.danc.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat

private val LightColors = lightColorScheme(
    primary = Forest,
    onPrimary = PureWhite,
    primaryContainer = LeafSoft,
    onPrimaryContainer = ForestHover,
    secondary = Sage,
    onSecondary = PureWhite,
    tertiary = Moss,
    onTertiary = Stone900,
    background = Cream,
    onBackground = Stone900,
    surface = PureWhite,
    onSurface = Stone900,
    surfaceVariant = CreamDark,
    onSurfaceVariant = Stone600,
    error = Red500,
    onError = PureWhite,
    errorContainer = CreamDark,
    onErrorContainer = Red600,
    outline = Stone200,
    outlineVariant = Stone200
)

private val DarkColors = darkColorScheme(
    primary = DarkForest,
    onPrimary = BtnPrimaryText,
    primaryContainer = DarkLeafSoft,
    onPrimaryContainer = DarkForestHover,
    secondary = DarkSage,
    onSecondary = BtnPrimaryText,
    tertiary = DarkMoss,
    onTertiary = BtnPrimaryText,
    background = DarkCream,
    onBackground = DarkStone900,
    surface = DarkCreamDark,
    onSurface = DarkStone900,
    surfaceVariant = DarkWhite,
    onSurfaceVariant = DarkStone600,
    error = Red400,
    onError = BtnPrimaryText,
    errorContainer = DarkLeafSoft,
    onErrorContainer = Red400,
    outline = DarkStone200,
    outlineVariant = DarkStone200
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp)
)

@Composable
fun PanelsTheme(
    themeMode: String = "light",
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
