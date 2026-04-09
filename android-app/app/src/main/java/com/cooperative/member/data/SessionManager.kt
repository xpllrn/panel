package com.cooperative.member.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore("coop_session")

class SessionManager(private val context: Context) {

    private val store = context.dataStore
    private val accessKey = stringPreferencesKey("access_token")
    private val refreshKey = stringPreferencesKey("refresh_token")
    private val themeKey = stringPreferencesKey("theme_mode")
    private val deviceTokenKey = stringPreferencesKey("device_token")

    val isLoggedIn: Flow<Boolean> = store.data.map { prefs ->
        !prefs[accessKey].isNullOrEmpty()
    }

    val themeMode: Flow<String> = store.data.map { prefs ->
        prefs[themeKey] ?: "light"
    }

    suspend fun syncCacheFromStorage() {
        TokenCache.accessToken = store.data.map { it[accessKey] }.first()
    }

    suspend fun saveTokens(access: String, refresh: String) {
        TokenCache.accessToken = access
        store.edit { prefs ->
            prefs[accessKey] = access
            prefs[refreshKey] = refresh
        }
    }

    suspend fun saveThemeMode(mode: String) {
        store.edit { it[themeKey] = mode }
    }

    suspend fun clearSession() {
        TokenCache.accessToken = null
        store.edit { prefs ->
            prefs.remove(accessKey)
            prefs.remove(refreshKey)
        }
    }

    suspend fun getRefreshToken(): String? {
        return store.data.map { it[refreshKey] }.first()
    }

    suspend fun getAccessToken(): String? {
        return store.data.map { it[accessKey] }.first()
    }

    suspend fun saveDeviceToken(token: String) {
        store.edit { it[deviceTokenKey] = token }
    }

    suspend fun getDeviceToken(): String? {
        return store.data.map { it[deviceTokenKey] }.first()
    }

    suspend fun clearDeviceToken() {
        store.edit { it.remove(deviceTokenKey) }
    }
}
