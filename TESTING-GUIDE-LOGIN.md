# Quick Testing Guide - Login Frontend

## Prerequisites

### 1. Ensure Backend JWT is Running
```bash
# Terminal 1: Start backend (dari d:\aqil\pusdatik\backend)
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Ensure Frontend Dev Server is Running
```bash
# Terminal 2: Start frontend (dari d:\aqil\pusdatik\frontend)
cd frontend
npm run dev
```

Frontend akan jalan di: **http://localhost:5173**

---

## Test Credentials

| Email | Password | Role |
|-------|----------|------|
| admin@bssn.go.id | password123 | admin |
| user@bssn.go.id | password123 | user |

Kedua users sudah tersimpan di database SQLite dengan password yang di-hash menggunakan bcrypt.

---

## Testing Scenarios

### ✅ Scenario 1: Successful Login
1. Go to http://localhost:5173/login
2. Enter: `admin@bssn.go.id`
3. Enter: `password123`
4. Click "MASUK →"
5. **Expected**: Redirect to home page (http://localhost:5173/)

### ❌ Scenario 2: Invalid Credentials
1. Go to http://localhost:5173/login
2. Enter: `admin@bssn.go.id`
3. Enter: `wrongpassword`
4. Click "MASUK →"
5. **Expected**: Error message "Email atau password salah." appears

### ❌ Scenario 3: Non-existent Email
1. Go to http://localhost:5173/login
2. Enter: `nonexistent@example.com`
3. Enter: `password123`
4. Click "MASUK →"
5. **Expected**: Error message "Email atau password salah." appears

### ⚠️ Scenario 4: Empty Fields
1. Go to http://localhost:5173/login
2. Leave both fields empty
3. Try to click "MASUK →"
4. **Expected**: Browser shows "Please fill out this field" messages (HTML5 validation)

### 🔄 Scenario 5: Logout & Re-login
1. After successful login at home page
2. Look for logout option (may be in topbar or documents page)
3. Click logout
4. Should redirect to login page
5. Login again with valid credentials
6. **Expected**: Successfully logged in again

### 📱 Scenario 6: Responsive Design
1. Open login page
2. Press F12 to open DevTools
3. Click device toolbar icon
4. Test on different devices:
   - iPhone 12 (390x844)
   - iPad (768x1024)
   - Desktop (1920x1080)
5. **Expected**: Layout adapts properly on all sizes

---

## UI Verification Checklist

### Header & Branding
- [ ] Topbar displays "SPBE Asisten"
- [ ] Topbar displays "Badan Siber dan Sandi Negara"
- [ ] Logo "B" is visible in gold color

### Form Layout
- [ ] Lock icon (🔒) is visible
- [ ] Title "Autentikasi Sistem" is displayed
- [ ] Subtitle text is visible
- [ ] Email input has placeholder "admin@bssn.go.id"
- [ ] Password input has placeholder "••••••••"
- [ ] "MASUK →" button is gold colored

### Color & Styling
- [ ] Navy background gradient is visible
- [ ] Card has white background with gold top border
- [ ] Input fields have light background
- [ ] Button is gold (#c9a84c)
- [ ] Text colors match design system

### Interactions
- [ ] Email input changes color on focus
- [ ] Password input changes color on focus
- [ ] Button shows darker gold on hover
- [ ] Loading spinner appears while submitting
- [ ] Error message shows in red if login fails
- [ ] Error has icon before text
- [ ] Check mark appears next to filled email field

### Accessibility
- [ ] Can tab through email → password → button
- [ ] Tab order is logical
- [ ] Labels are associated with inputs
- [ ] Error messages are readable
- [ ] Can submit with Enter key

---

## Console Logging

Open browser console (F12 → Console tab) to see:

```javascript
// On successful login:
// 1. POST /api/auth/login request
// 2. Response with access_token

// On error:
// 1. Failed request logged
// 2. Error type (401, 500, network)

// Token check:
// Run in console: localStorage.getItem('spbe_access_token')
// Should return: jwt_token_here or null if not logged in
```

---

## Troubleshooting

### Issue: CORS Error
**Solution**: Check backend is running and accessible at http://localhost:8000

### Issue: 404 on /login route
**Solution**: Check router.js has login route configured

### Issue: Token not stored
**Solution**: Check auth.js `login()` function stores token in localStorage

### Issue: Redirect not working
**Solution**: Check router has auth guards and redirect logic

### Issue: Styling looks broken
**Solution**: 
1. Hard refresh: Ctrl+Shift+R
2. Check main.css is loaded
3. Check design system variables are defined

### Issue: Tests fail locally
**Solution**:
```bash
cd frontend
npm install  # Ensure dependencies installed
npm test -- LoginView.test.js --reporter=verbose
```

---

## Browser DevTools Debugging

### Network Tab
- Click "MASUK →"
- Check POST /api/auth/login request
- Verify response contains `access_token`
- Check request payload format

### Storage Tab
- Go to Application → Storage → Local Storage
- Check for key: `spbe_access_token`
- Verify token is stored after login

### Elements Tab
- Inspect email input
- Verify it has `id="email"` matching label
- Verify has `required` attribute
- Verify has `type="email"`

### Console Tab
- Check for any JavaScript errors
- Look for login attempt logs
- Check router navigation logs

---

## Expected User Flow

```
┌─────────────────┐
│  Login Page     │
│  (http://5173)  │
├─────────────────┤
│ Email: ____     │
│ Password: ____  │
│ [MASUK →]       │
└────────┬────────┘
         │
    User enters credentials
         │
         ▼
    Submit form
         │
         ▼
    POST /api/auth/login
         │
    ┌────┴─────┐
    │           │
   200        401/500
    │           │
    ▼           ▼
 Store       Show error
 Token       message
    │           │
    ▼           │
 Redirect    Stay on page
 to home        (can retry)
    │
    ▼
┌──────────────┐
│  Home Page   │
│  (logged in) │
└──────────────┘
```

---

## Performance Notes

- Login page load: < 1s (with frontend server running)
- Login submission: < 2s (with backend server responding)
- Token validation: Instant (local check)
- Redirect: < 500ms (router transition)

---

## Next Integration Points

Once login works:

1. ✅ **Chat Page** - Verify auth guard redirects to login
2. ✅ **Documents Page** - Same auth guard check
3. ✅ **Session Sidebar** - Should load user sessions
4. ✅ **Logout** - From any page should clear token and redirect to login
5. ✅ **Token Refresh** - Auto-refresh on 401 responses
6. ✅ **Role-based Access** - Different views for admin/user roles

---

## Quick Verification Commands

```bash
# Check backend health
curl http://localhost:8000/api/health

# Check frontend is serving
curl http://localhost:5173

# Verify vitest tests
cd frontend && npm test -- LoginView.test.js

# Check git commits
git log --oneline -5
```

---

**Happy Testing! 🎉**
