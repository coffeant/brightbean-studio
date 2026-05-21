# Fix Social Platform OAuth Connections

## Summary
Fix OAuth connection errors for TikTok, YouTube, and Pinterest across the providers layer and the OAuth callback views. Also document remaining user-side config needed in developer consoles.

## Already Fixed (applied directly — verify before proceeding)
These changes were applied during investigation. The plan assumes they are correct:
- `providers/facebook.py`: Removed invalid scopes `pages_read_user_content` and `pages_read_user_engagement` from `required_scopes`
- `providers/instagram.py`: Added `display=page` and `extras={"setup":{"channel":"IG_API_ONBOARDING"}}` to `get_auth_url()`
- `providers/linkedin_company.py`: Replaced `r_basicprofile` → `openid`, `profile`, `email`; added `get_profile()` using `/v2/userinfo`
- `providers/linkedin_personal.py`: Replaced `r_basicprofile` → OIDC scopes; removed `r_member_social`; `get_profile()` always uses `/v2/userinfo`

---

## Task 1: Fix TikTok PKCE (code_challenge / code_verifier)

**Problem**: TikTok OAuth v2 requires PKCE. The OAuth flow:
1. Generate `code_verifier` (random string)
2. Compute `code_challenge = base64url(sha256(code_verifier))`
3. Pass `code_challenge` + `code_challenge_method=S256` to TikTok auth URL
4. Pass `code_verifier` back when exchanging the authorization code

Current code does none of this.

### Subtask 1.1: Update TikTokProvider `[DONE]`

**File**: `providers/tiktok.py`

Add PKCE support to two methods:

**`get_auth_url()`** — Add `code_challenge` and `code_challenge_method` params if `code_challenge` is present in `self.credentials`:
```python
if "code_challenge" in self.credentials:
    params["code_challenge"] = self.credentials["code_challenge"]
    params["code_challenge_method"] = "S256"
```

**`exchange_code()`** — Add `code_verifier` to POST data if present in `self.credentials`:
```python
if "code_verifier" in self.credentials:
    data["code_verifier"] = self.credentials["code_verifier"]
```

### Subtask 1.2: Update connect_platform view `[DONE]`

**File**: `apps/social_accounts/views.py`

In the `connect_platform` function, before calling `provider.get_auth_url()`, add TikTok PKCE handling:
```python
import hashlib
import base64

# In connect_platform(), after creating session dict:
if platform == PlatformCredential.Platform.TIKTOK:
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    request.session[OAUTH_SESSION_KEY]["code_verifier"] = code_verifier
    provider = _get_provider_for_platform(
        platform, request.org.id,
        code_verifier=code_verifier,
        code_challenge=code_challenge,
    )
```

Note: `secrets` is already imported. Need to add `hashlib` and `base64` imports.

### Subtask 1.3: Update oauth_callback view `[DONE]`

**File**: `apps/social_accounts/views.py`

In the `oauth_callback` function, extract `code_verifier` from session and pass to TikTok provider:
```python
# After session_data = request.session.pop(...)
if platform == PlatformCredential.Platform.TIKTOK:
    extra_creds["code_verifier"] = session_data.get("code_verifier", "")
```

### Verification `[CODE DONE - AWAITING USER TEST]`
1. Navigate to Social Accounts → Connect → TikTok
2. OAuth redirect should succeed without "code_challenge" error
3. Token exchange should complete successfully

---

## Task 2: Fix YouTube OAuth 401 `invalid_client` `[BLOCKED - USER ACTION NEEDED]`

**Problem**: `PLATFORM_GOOGLE_CLIENT_ID` and `PLATFORM_GOOGLE_CLIENT_SECRET` in `.env` are set to **LinkedIn credentials** (`86o8ql1hd5nu8p` / `WPL_AP1...`), not actual Google Cloud OAuth credentials.

### Subtask 2.1: Create Google Cloud OAuth credentials

User needs to:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create an OAuth 2.0 Client ID (Web application type)
3. Add redirect URI: `http://localhost:8000/social-accounts/callback/youtube/`
4. Copy the Client ID and Client Secret
5. Enable YouTube Data API v3: https://console.cloud.google.com/apis/library/youtube.googleapis.com

### Subtask 2.2: Update .env with correct values

Replace current LinkedIn-looking values:
```
PLATFORM_GOOGLE_CLIENT_ID=<actual-google-client-id>
PLATFORM_GOOGLE_CLIENT_SECRET=<actual-google-client-secret>
```

### Verification
1. Navigate to Social Accounts → Connect → YouTube
2. Should show Google OAuth consent screen, not "OAuth client was not found"

---

## Task 3: Fix Pinterest OAuth credentials `[BLOCKED - USER ACTION NEEDED]`

**Problem**: `PLATFORM_PINTEREST_APP_ID` and `PLATFORM_PINTEREST_APP_SECRET` in `.env` are also set to **LinkedIn credentials**, not actual Pinterest app credentials.

### Subtask 3.1: Create Pinterest app

User needs to:
1. Go to https://developers.pinterest.com/apps/
2. Create a new app or find existing app
3. Get App ID and App Secret
4. Add redirect URI: `http://localhost:8000/social-accounts/callback/pinterest/`

### Subtask 3.2: Update .env with correct values
```
PLATFORM_PINTEREST_APP_ID=<actual-pinterest-app-id>
PLATFORM_PINTEREST_APP_SECRET=<actual-pinterest-app-secret>
```

---

## Task 4: Document remaining user-side developer console configurations

These are NOT code fixes — the user must complete these in each platform's developer console:

### Facebook
- [ ] App must be switched from Development to Live mode (or user added as developer/test user)
- [ ] Add `http://localhost:8000/social-accounts/callback/facebook/` to Valid OAuth Redirect URIs (Facebook Login → Settings)
- [ ] Add `localhost` to App Domains (App Settings → Basic)
- [ ] Set Privacy Policy URL and Category (App Settings → Basic)

### Instagram (via Facebook Login)
- [ ] Add **Instagram** product in App Dashboard → Add Product
- [ ] In **Use Cases** → Manage everything on your Page → Customize → Permissions:
  - `instagram_basic` — Ready for testing
  - `instagram_content_publish` — Ready for testing
  - `instagram_manage_comments` — Ready for testing
  - `instagram_manage_insights` — Ready for testing
- [ ] Add `http://localhost:8000/social-accounts/callback/instagram/` to Valid OAuth Redirect URIs

### LinkedIn Company Page
- [ ] `w_organization_social` scope requires **Community Management API** approval from LinkedIn
- [ ] Apply at: https://www.linkedin.com/developers/apps/ → Products → Community Management API → Request Access
- [ ] Without this approval, LinkedIn Company Page posting won't work

---

## Files Modified
| File | Change |
|------|--------|
| `providers/tiktok.py` | Add PKCE (code_challenge in get_auth_url, code_verifier in exchange_code) |
| `apps/social_accounts/views.py` | Generate PKCE params for TikTok in connect_platform; pass code_verifier in oauth_callback |
| `.env` | Fix PLATFORM_GOOGLE_CLIENT_ID/SECRET and PLATFORM_PINTEREST_APP_ID/SECRET (user action) |

## Verification Wave
After all tasks:
- [ ] TikTok connects without "code_challenge" error `[CODE DONE - needs user test]`
- [ ] YouTube redirects to Google OAuth consent screen (not 401) `[BLOCKED - needs Google OAuth creds]`
- [ ] Pinterest connects successfully `[BLOCKED - needs Pinterest app creds]`
- [ ] Facebook connects (requires developer console config) `[USER ACTION]`
- [ ] Instagram connects (requires developer console config) `[USER ACTION]`
- [ ] LinkedIn Personal connects (already tested — should work)
- [ ] LinkedIn Company connects (requires Community Management API approval) `[USER ACTION]`

## Rollback
If TikTok PKCE changes break existing TikTok auth:
- Revert `get_auth_url()` to original (remove code_challenge logic)
- Revert `exchange_code()` to original (remove code_verifier logic)
- Remove PKCE handling in views.py
