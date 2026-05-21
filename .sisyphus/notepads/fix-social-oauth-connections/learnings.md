# Fix Social OAuth Connections - Progress Log

## Already Fixed (verified from codebase read)
- [x] Facebook: removed invalid scopes `pages_read_user_content`, `pages_read_user_engagement`
- [x] Instagram: added `display=page` + `extras={"setup":{"channel":"IG_API_ONBOARDING"}}` to `get_auth_url()`
- [x] LinkedIn Company: OIDC scopes (`openid`, `profile`, `email`) + `/v2/userinfo` for `get_profile()`
- [x] LinkedIn Personal: OIDC scopes + `/v2/userinfo` for `get_profile()`

## Task 1: TikTok PKCE — DONE (code changes applied)
- [x] Subtask 1.1: `providers/tiktok.py` — `get_auth_url()` adds code_challenge; `exchange_code()` adds code_verifier
- [x] Subtask 1.2: `apps/social_accounts/views.py` — `connect_platform()` generates PKCE params for TikTok, stores code_verifier in session, recreates provider with creds
- [x] Subtask 1.3: `apps/social_accounts/views.py` — `oauth_callback()` extracts code_verifier from session, passes to provider

## Task 2: YouTube OAuth 401 — BLOCKED (user action)
- Problem: `PLATFORM_GOOGLE_CLIENT_ID` / `SECRET` in `.env` are LinkedIn credentials (`86o8ql1hd5nu8p` / `WPL_AP1...`)
- YouTube provider (`providers/youtube.py`) reads `client_id` / `client_secret` from credentials dict
- Settings (`config/settings/base.py` line 307-308) maps env -> creds as `PLATFORM_GOOGLE_CLIENT_ID` / `PLATFORM_GOOGLE_CLIENT_SECRET`
- Need: user to create Google Cloud OAuth 2.0 Web client, enable YouTube Data API v3
- `.env.example` already has correct placeholders

## Task 3: Pinterest OAuth — BLOCKED (user action)
- Problem: `PLATFORM_PINTEREST_APP_ID` / `SECRET` in `.env` are LinkedIn credentials (`86o8ql1hd5nu8p` / `WPL_AP1...`)
- Pinterest provider (`providers/pinterest.py`) normalizes `app_id` → `client_id`, `app_secret` → `client_secret`
- Settings (`config/settings/base.py` lines 371-372) maps env -> creds
- Need: user to create Pinterest app at developers.pinterest.com
- `.env.example` already has correct placeholders

## Task 4: Developer Console Setup Docs — COVERED by plan
- Facebook: Live mode, redirect URIs, App Domains, Privacy Policy
- Instagram: Add product, scopes, redirect URIs
- LinkedIn Company Page: Community Management API approval

## Verification Wave — BLOCKED (needs user testing + creds)
- TikTok: PKCE changes should fix "code_challenge missing" error
- YouTube: needs valid Google OAuth creds
- Pinterest: needs valid Pinterest app creds
- Facebook/Instagram: needs developer console config
- LinkedIn Personal: already tested - should work
- LinkedIn Company: needs Community Management API approval
