# Android App Troubleshooting

## Login Credentials

### Demo Member Account
- **Username**: `sureshdesai1`
- **Password**: `demo1234`

### Admin Account (for web portal)
- **Username**: `admin`
- **Password**: `admin123`

## Common Issues

### 1. "Cannot connect to server" Error

**Cause**: The Django backend is not running or not accessible.

**Solution**:
```bash
# Check if Docker containers are running
docker ps

# If not running, start them
docker-compose up -d

# Check if API is accessible
curl http://localhost:8000/api/v1/
```

### 2. "No internet connection" Error

**Cause**: The emulator cannot reach the host machine or Django ALLOWED_HOSTS is not configured.

**Solution**:
- The app uses `http://10.0.2.2:8000` which is the special IP for Android emulator
- Make sure Docker is exposing port 8000: `docker ps` should show `0.0.0.0:8000->8000/tcp`
- Check `.env` file has: `ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2,0.0.0.0`
- Restart Django after changing .env: `docker-compose restart web`
- Try accessing from your browser: http://localhost:8000/api/v1/

### 3. "Invalid username or password" Error

**Cause**: User doesn't exist or password is wrong.

**Solution**:
```bash
# Reset demo user password
docker exec panel-web-1 python manage.py shell -c "
from accounts.models import User
user = User.objects.get(username='sureshdesai1')
user.set_password('demo1234')
user.save()
print('Password reset to: demo1234')
"
```

### 4. App crashes on login

**Check Android Logcat**:
1. Open Android Studio
2. Go to View → Tool Windows → Logcat
3. Filter by "cooperative" or "error"
4. Look for the actual error message

### 5. Using Physical Device Instead of Emulator

If using a physical device, you need to change the API URL:

1. Find your Mac's local IP:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

2. Update `android-app/app/build.gradle.kts`:
```kotlin
buildConfigField("String", "API_BASE_URL", "\"http://YOUR_IP:8000/api/v1\"")
```

3. Rebuild the app

## Testing the API

### Test Login Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"sureshdesai1","password":"demo1234"}'
```

### Test Dashboard Endpoint
```bash
# First get the access token from login, then:
curl http://localhost:8000/api/v1/member/dashboard/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Creating New Demo Users

```bash
# Create a single user
docker exec panel-web-1 python manage.py shell -c "
from accounts.models import User
user = User.objects.create_user(
    username='newuser',
    password='password123',
    email='newuser@example.com',
    first_name='New',
    last_name='User',
    role='member',
    status='active'
)
print(f'Created: {user.username}')
"

# Or create multiple demo users with data
docker exec panel-web-1 python manage.py create_complete_demo_data --count 5
```

## Network Configuration

The app is configured to use:
- **Emulator**: `http://10.0.2.2:8000/api/v1` (maps to host's localhost)
- **Physical Device**: Need to use actual IP address

## Checking Server Status

```bash
# Check if containers are running
docker ps

# Check server logs
docker logs panel-web-1

# Check if API is responding
curl http://localhost:8000/api/v1/
```
