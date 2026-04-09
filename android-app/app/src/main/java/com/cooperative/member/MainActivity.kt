package com.cooperative.member

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.lifecycleScope
import com.google.firebase.messaging.FirebaseMessaging
import com.cooperative.member.ui.navigation.AppNavigation
import com.cooperative.member.ui.theme.CooperativeTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val app = application as CooperativeApp

        lifecycleScope.launch {
            app.session.syncCacheFromStorage()
            runCatching {
                FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                    lifecycleScope.launch {
                        app.repository.registerDeviceToken(token)
                    }
                }
            }
        }

        setContent {
            val theme by app.session.themeMode.collectAsState(initial = "light")
            CooperativeTheme(themeMode = theme) {
                AppNavigation()
            }
        }
    }
}
