package com.panels.danc

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import com.panels.danc.ui.navigation.AppNavigation
import com.panels.danc.ui.theme.PanelsTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val app = application as CooperativeApp

        setContent {
            val theme by app.session.themeMode.collectAsState(initial = "light")
            PanelsTheme(themeMode = theme) {
                AppNavigation()
            }
        }
    }
}
