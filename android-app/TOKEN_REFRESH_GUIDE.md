# Token Refresh Implementation Guide

## What Was Implemented

Automatic token refresh has been added to keep users logged in without interruption. When the access token expires (401 error), the app will automatically:

1. Use the refresh token to get a new access token
2. Retry the failed request with the new token
3. If refresh fails, log the user out

## Changes Made

### 1. AuthInterceptor.kt

- Now intercepts 401 responses
- Automatically calls `/auth/refresh/` endpoint
- Retries the original request with new token
- Clears session if refresh fails

### 2. ApiClient.kt

- Updated to pass `SessionManager` to `AuthInterceptor`
- Added `createRefreshService()` method (without auth interceptor to avoid recursion)

### 3. SessionManager.kt

- Already had `getRefreshToken()` method (no changes needed)

## How to Test

### Step 1: Build and Run

1. In Android Studio: `Build` → `Clean Project`
2. Then: `Build` → `Rebuild Project`
3. Clear app data or uninstall the app
4. Run the app (green play button)

### Step 2: Test Token Refresh

The access token typically expires after 15-60 minutes (depending on backend settings).

**Option A: Wait for natural expiration**

1. Login to the app
2. Leave the app open or in background
3. Wait for token to expire
4. Try to navigate or refresh data
5. App should automatically refresh token and continue working

**Option B: Force token expiration (for quick testing)**

1. Login to the app
2. In Android Studio, go to `Device File Explorer`
3. Navigate to: `/data/data/com.cooperative.member/files/datastore/`
4. Delete or modify the `coop_session.preferences_pb` file
5. Try to use the app - it should handle the error gracefully

### Step 3: Verify Logs

In Android Studio's Logcat, filter by "okhttp" to see:

- Initial request with access token
- 401 response
- Refresh token request
- New access token received
- Original request retried successfully

## Expected Behavior

### Success Case

```
1. User makes API request → 401 Unauthorized
2. App calls /auth/refresh/ with refresh token
3. Backend returns new access token
4. App retries original request with new token
5. User sees no interruption
```

### Failure Case

```
1. User makes API request → 401 Unauthorized
2. App calls /auth/refresh/ with refresh token
3. Refresh token is invalid/expired → 401
4. App clears session and redirects to login
```

## Backend Requirements

Your Django backend already has the `/auth/refresh/` endpoint configured. Make sure:

1. **Endpoint exists**: `POST /api/v1/auth/refresh/`
2. **Request format**: `{"refresh": "your_refresh_token"}`
3. **Response format**: `{"access": "new_access_token"}`
4. **Token expiration**: Access tokens should expire (e.g., 1 hour), refresh tokens last longer (e.g., 7 days)

## Troubleshooting

### Issue: Still getting logged out

- Check if refresh token is being saved properly
- Verify backend `/auth/refresh/` endpoint is working
- Check Logcat for error messages

### Issue: Infinite loop of refresh requests

- This shouldn't happen due to the check: `!request.url.encodedPath.contains("/auth/refresh/")`
- If it does, check backend response codes

### Issue: App crashes on token refresh

- Check Logcat for stack trace
- Verify `RefreshRequest` and `RefreshResponse` models match backend

## Additional Improvements (Optional)

### 1. Add Token Expiration Tracking

Store token expiration time and refresh proactively before it expires:

```kotlin
// In SessionManager.kt
private val expiresAtKey = longPreferencesKey("token_expires_at")

suspend fun saveTokensWithExpiry(access: String, refresh: String, expiresIn: Long) {
    val expiresAt = System.currentTimeMillis() + (expiresIn * 1000)
    store.edit { prefs ->
        prefs[accessKey] = access
        prefs[refreshKey] = refresh
        prefs[expiresAtKey] = expiresAt
    }
}

suspend fun isTokenExpired(): Boolean {
    val expiresAt = store.data.map { it[expiresAtKey] ?: 0L }.first()
    return System.currentTimeMillis() >= expiresAt
}
```

### 2. Add Refresh Lock

Prevent multiple simultaneous refresh requests:

```kotlin
private val refreshLock = Mutex()

private suspend fun refreshAccessToken(): Boolean {
    refreshLock.withLock {
        // refresh logic here
    }
}
```

### 3. Add User Notification

Show a subtle message when token is refreshed:

```kotlin
// In your ViewModel
viewModelScope.launch {
    snackbarHostState.showSnackbar("Session refreshed")
}
```

## Summary

✅ Automatic token refresh implemented
✅ Users stay logged in longer
✅ Seamless experience with no interruptions
✅ Graceful logout when refresh fails

The app will now handle token expiration automatically!