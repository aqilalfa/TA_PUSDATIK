# UI-SPEC: LoginView Component

> **Status**: Design Contract for TDD Implementation
> **Audience**: Frontend developers building authentication UI
> **Date**: May 12, 2026

---

## 1. Component Overview

**LoginView** is the authentication portal for SPBE RAG system. It provides a secure, institutional-looking login interface aligned with BSSN branding.

- **Route**: `/login`
- **Access**: Public (unauthenticated users only)
- **Layout**: Full-page centered card design
- **Redirect Logic**: After login, redirect to requested page or `/` (home)

---

## 2. Visual Design & Layout

### 2.1 Color & Typography

| Element | Color | Typography | Purpose |
|---------|-------|-----------|---------|
| Background Gradient | Navy → Navy-Dark | — | Institutional, secure feel |
| Card Background | White | — | Content container |
| Card Border-Top | Gold | — | Branding accent |
| Header Icon | — | Large emoji (🔒) | Visual anchor |
| Title | Navy | Playfair Display, 24px, bold | Primary heading |
| Subtitle | Navy-Muted | Source Serif 4, 14px | Descriptive text |
| Label | Navy-Dark | IBM Plex Sans, 12px, 600wt | Form labels |
| Input Text | Navy-Dark | IBM Plex Sans, 14px | Form input |
| Error Text | Red (#d32f2f) | IBM Plex Sans, 12px | Error messages |
| Button Text | White | IBM Plex Sans, 12px, 600wt | Call-to-action |
| Footer Text | Muted Gray | IBM Plex Sans, 11px | Helper text |

### 2.2 Layout Grid

```
┌──────────────────────────────────────────┐
│  [TOPBAR] SPBE Asisten · BSSN            │  ← Topbar (consistent with home/docs)
├──────────────────────────────────────────┤
│                                          │
│            ┌─────────────────────┐      │
│            │  🔒                 │      │
│            │  Autentikasi Sistem │      │  ← Card centered vertically
│            │  [Subtitle]         │      │
│            │  ─────────────────  │      │
│            │  [Email Input]      │      │
│            │  [Password Input]   │      │
│            │  [LOGIN →]          │      │
│            │  [Footer Text]      │      │
│            └─────────────────────┘      │
│                                          │
└──────────────────────────────────────────┘
```

### 2.3 Responsive Breakpoints

| Breakpoint | Width | Card Width | Padding |
|-----------|-------|-----------|---------|
| Mobile | < 600px | 90% | 20px h-sides, 30px v-sides |
| Tablet | 600px-1024px | 420px | 30px h-sides, 35px v-sides |
| Desktop | > 1024px | 420px | 40px h-sides, 40px v-sides |

---

## 3. Component States & Interactions

### 3.1 Form State Machine

```
[Idle] → [Loading] → [Success] → [Redirect]
  ↓
[Error] → [Idle] (user corrects input)
```

### 3.2 Input Field States

| State | Appearance | Behavior |
|-------|-----------|----------|
| **Default** | Border gray, placeholder visible | Cursor in field |
| **Focus** | Border navy, bottom shadow | Input active |
| **Filled** | Border navy-light, text visible | Value persisted |
| **Error** | Border red, error icon visible | Message shown below |
| **Disabled** | Opacity 0.5, no interaction | During submission |

### 3.3 Button States

| State | Appearance | Behavior |
|-------|-----------|----------|
| **Default** | Background gold, text navy | Hover: darker gold |
| **Hover** | Background gold-hover | Cursor pointer |
| **Active** | Slight press-down effect | Visual feedback |
| **Loading** | Spinner visible, text hidden | Button disabled |
| **Disabled** | Opacity 0.5, no interaction | During submission |

### 3.4 Error Scenarios

| Scenario | Message | Duration | Dismissal |
|----------|---------|----------|-----------|
| Invalid credentials | "Email atau password salah." | Persistent | Auto-clear on re-submit |
| Network error | "Terjadi kesalahan pada sistem. Silakan coba lagi." | Persistent | Auto-clear on re-submit |
| Validation failed | "Email tidak valid." / "Password minimal 6 karakter." | Persistent | Auto-clear on input change |

---

## 4. Form Validation Rules

### 4.1 Email Field
- **Type**: `email`
- **Required**: Yes
- **Pattern**: Standard email regex
- **Error Message**: "Masukkan alamat email yang valid"
- **Placeholder**: `admin@bssn.go.id`

### 4.2 Password Field
- **Type**: `password`
- **Required**: Yes
- **Min Length**: 6 characters (frontend validation)
- **Max Length**: 128 characters
- **Error Message**: "Password minimal 6 karakter"
- **Placeholder**: `••••••••`
- **Show/Hide Toggle**: Optional (consider adding toggle icon)

---

## 5. Accessibility & UX

### 5.1 WCAG Compliance
- ✅ All form inputs have associated `<label>` elements
- ✅ Error messages linked to inputs via `aria-describedby`
- ✅ Loading state announced via `aria-busy="true"`
- ✅ Keyboard navigation: Tab through inputs → button
- ✅ Color not sole indicator of error (icon + text)

### 5.2 Best Practices
- Placeholders should not replace labels
- Error messages should be specific and actionable
- Loading indicator prevents multiple submissions
- Focus visible on all interactive elements
- Form submittable via Enter key

---

## 6. API Integration

### 6.1 Login Flow
```
1. User enters email + password
2. Click "MASUK →" button
3. POST /api/auth/login (OAuth2PasswordRequestForm)
4. Backend returns: { access_token, token_type, expires_in }
5. Store token in localStorage
6. Redirect to requested page or home
```

### 6.2 Error Handling
```
- 401: Invalid credentials → Show "Email atau password salah."
- 400: Validation failed → Show field-specific error
- 500+: Server error → Show "Terjadi kesalahan pada sistem..."
- Network error → Show connection error message
```

---

## 7. Component Files & Structure

```
frontend/src/
├── views/
│   └── LoginView.vue ← Main component
├── components/
│   ├── common/
│   │   ├── FormInput.vue ← Reusable form input
│   │   └── FormButton.vue ← Reusable button
├── services/
│   └── auth.js ← Existing auth service
└── tests/
    ├── unit/
    │   └── LoginView.test.js ← Test suite
    └── e2e/
        └── login.e2e.js ← E2E tests
```

---

## 8. CSS Styling Approach

### 8.1 Design Tokens (from main.css)
```css
/* Already available */
--color-navy: #1a3a6b
--color-navy-dark: #122d57
--color-gold: #c9a84c
--color-cream: #f8f7f4
--font-display: 'Playfair Display'
--font-ui: 'IBM Plex Sans'
```

### 8.2 New Token Definitions
```css
--color-input-border: #d0d0d0
--color-input-border-focus: #1a3a6b
--color-error-bg: #ffebee
--color-error-border: #d32f2f
--color-error-text: #d32f2f
--spacing-form-gap: 16px
--spacing-card-padding: 40px
--border-radius-card: 4px
```

---

## 9. Animation & Micro-Interactions

### 9.1 Transitions
- Input focus: 150ms ease-in-out
- Button hover: 150ms ease-in-out
- Error fade-in: 200ms ease-out
- Loading spinner: Continuous (1s per rotation)

### 9.2 Animations
- Card entrance: Fade-in + subtle scale (200ms)
- Form submission: Button spinner animation
- Error appearance: Slide-down + fade-in

---

## 10. Validation Matrix (6 Pillars)

| Pillar | Pass Criteria | Status |
|--------|---------------|--------|
| **Visual Design** | Matches Navy/Gold/Cream palette, Playfair + IBM Plex | ⏳ Pending |
| **UX Flow** | Form → Validation → Loading → Success/Error | ⏳ Pending |
| **Accessibility** | WCAG AA, keyboard nav, proper labels | ⏳ Pending |
| **Responsive** | Works on mobile, tablet, desktop | ⏳ Pending |
| **Performance** | Fast interaction feedback, no jank | ⏳ Pending |
| **Error Handling** | Clear messages for all failure scenarios | ⏳ Pending |

---

## 11. QA Checklist

### Before Implementation Review
- [ ] Design approved by stakeholder
- [ ] Color contrast ratio ≥ 4.5:1 (WCAG AA)
- [ ] Responsive layout tested on 3+ screen sizes
- [ ] Keyboard navigation verified
- [ ] Touch/mobile UX verified

### After Implementation Review
- [ ] All unit tests passing
- [ ] E2E tests for happy path + error flows
- [ ] Performance metrics: FCP < 1s, LCP < 2s
- [ ] Cross-browser tested (Chrome, Firefox, Safari, Edge)
- [ ] Mobile tested on real devices (iOS + Android)

---

## 12. Future Enhancements (Backlog)

- [ ] "Remember me" checkbox (persist login across sessions)
- [ ] Password recovery flow (`/forgot-password`)
- [ ] Social login (if applicable for BSSN)
- [ ] 2FA integration
- [ ] LDAP integration toggle in settings
- [ ] Password strength meter
- [ ] Rate limiting UI feedback
