# Cooperative Society Member App (Android)

A native Android app built with Kotlin and Jetpack Compose for cooperative society members to view their accounts, loans, and transactions.

## Features

- **Secure Login** with JWT authentication
- **Dashboard** with member profile, share capital, accounts, and loans summary
- **Account Details** with transaction history
- **Loan Details** with complete EMI repayment schedule
- **All Transactions** view across all accounts
- **Material Design 3** UI with modern Jetpack Compose
- **Offline token storage** using DataStore
- **Automatic token refresh** handling

## Tech Stack

- **Language**: Kotlin
- **UI**: Jetpack Compose with Material Design 3
- **Architecture**: MVVM with Repository pattern
- **Dependency Injection**: Hilt
- **Networking**: Retrofit + OkHttp
- **Async**: Kotlin Coroutines + Flow
- **Navigation**: Jetpack Navigation Compose
- **Secure Storage**: DataStore Preferences

## Project Structure

```
app/src/main/java/com/cooperative/member/
├── data/
│   ├── api/
│   │   ├── ApiService.kt          # Retrofit API endpoints
│   │   └── AuthInterceptor.kt     # JWT token injection
│   ├── model/                     # Data models
│   └── repository/                # Data repositories
├── di/
│   └── NetworkModule.kt           # Hilt dependency injection
├── ui/
│   ├── navigation/
│   │   └── AppNavigation.kt       # Navigation graph
│   ├── screens/                   # Composable screens
│   ├── theme/                     # Material Design theme
│   └── viewmodel/                 # ViewModels
├── util/
│   └── Resource.kt                # API response wrapper
├── CooperativeApp.kt              # Application class
└── MainActivity.kt                # Main activity
```

## Setup Instructions

### Prerequisites

- Android Studio Hedgehog (2023.1.1) or later
- JDK 17
- Android SDK 34
- Gradle 8.2+

### Configuration

1. **Clone the repository**

2. **Update API Base URL**

   Edit `app/build.gradle.kts`:
   ```kotlin
   buildConfigField("String", "API_BASE_URL", "\"http://YOUR_SERVER_IP:8000/api/v1\"")
   ```

   For local development:
   - Use `http://10.0.2.2:8000/api/v1` for Android Emulator
   - Use `http://YOUR_LOCAL_IP:8000/api/v1` for physical device

3. **Sync Gradle**

   Open the project in Android Studio and sync Gradle files.

### Build & Run

1. **Using Android Studio**:
   - Click "Run" button or press `Shift + F10`
   - Select your device/emulator

2. **Using Command Line**:
   ```bash
   # Debug build
   ./gradlew assembleDebug
   
   # Install on connected device
   ./gradlew installDebug
   
   # Run tests
   ./gradlew test
   ```

### Generate APK

```bash
# Debug APK
./gradlew assembleDebug
# Output: app/build/outputs/apk/debug/app-debug.apk

# Release APK (requires signing configuration)
./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release.apk
```

## API Integration

The app connects to the Django REST API documented in `/API_DOCUMENTATION.md`.

### Authentication Flow

1. User enters username and password
2. App calls `/api/v1/auth/login/` and receives JWT tokens
3. Tokens are stored securely in DataStore
4. Access token is automatically added to all API requests via `AuthInterceptor`
5. On 401 error, app attempts to refresh token using `/api/v1/auth/refresh/`

### Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `POST /auth/login/` | Login and get JWT tokens |
| `POST /auth/refresh/` | Refresh access token |
| `GET /auth/profile/` | Get member profile |
| `GET /member/dashboard/` | Dashboard data |
| `GET /member/accounts/` | List accounts |
| `GET /member/accounts/{id}/` | Account details |
| `GET /member/loans/` | List loans |
| `GET /member/loans/{id}/` | Loan details with EMI schedule |
| `GET /member/transactions/` | All transactions |

## Testing

### Test Credentials

Use the demo member accounts created by the Django management command:

```
Username: sureshdesai1
Password: 0210SURE
```

(Password format: DDMM + first 4 chars of name uppercase)

### Network Testing

For testing on physical device:
1. Ensure your device and server are on the same network
2. Update API_BASE_URL to your computer's local IP
3. Make sure Django's `ALLOWED_HOSTS` includes your IP

## Troubleshooting

### Connection Issues

- **Emulator**: Use `10.0.2.2` instead of `localhost`
- **Physical Device**: Use your computer's local IP address
- **CORS**: Ensure Django CORS settings allow your requests
- **Firewall**: Check if port 8000 is accessible

### Build Issues

```bash
# Clean build
./gradlew clean

# Invalidate caches in Android Studio
File > Invalidate Caches > Invalidate and Restart
```

### Token Issues

If you get 401 errors:
- Check if tokens are being saved (use Logcat)
- Verify token expiry times in Django settings
- Clear app data and login again

## Screenshots

(Add screenshots of your app here)

## Future Enhancements

- [ ] Push notifications for EMI reminders
- [ ] Biometric authentication
- [ ] Download transaction receipts as PDF
- [ ] Dark mode support
- [ ] Offline mode with local caching
- [ ] Multi-language support

## License

[Your License]

## Contact

For issues or questions, contact [Your Contact Info]
