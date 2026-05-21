"""Background tasks for social account health checks."""

import logging
from datetime import timedelta

from background_task import background
from django.utils import timezone

logger = logging.getLogger(__name__)


@background(schedule=0)
def check_social_account_health(account_id: str):
    """Check health of a single social account.

    Validates the OAuth token by calling get_profile(). If the token
    is expiring soon, attempts to refresh it first.
    """
    from providers import get_provider

    from .error_messages import friendly_health_check_error
    from .models import SocialAccount

    try:
        account = SocialAccount.objects.get(id=account_id)
    except SocialAccount.DoesNotExist:
        logger.warning("Health check: account %s not found, skipping", account_id)
        return

    # Load app credentials from the workspace's org or env fallback
    from django.conf import settings

    from apps.credentials.models import PlatformCredential

    credentials: dict = {}
    try:
        org_id = account.workspace.organization_id
        cred = PlatformCredential.objects.for_org(org_id).get(platform=account.platform, is_configured=True)
        credentials = cred.credentials
    except PlatformCredential.DoesNotExist:
        env_creds = getattr(settings, "PLATFORM_CREDENTIALS_FROM_ENV", {})
        credentials = env_creds.get(account.platform, {})

    # For Mastodon, inject instance-specific client credentials
    if account.platform == PlatformCredential.Platform.MASTODON and account.instance_url:
        from .models import MastodonAppRegistration

        try:
            reg = MastodonAppRegistration.objects.get(instance_url=account.instance_url)
            credentials = {
                **credentials,
                "instance_url": account.instance_url,
                "client_id": reg.client_id,
                "client_secret": reg.client_secret,
            }
        except MastodonAppRegistration.DoesNotExist:
            pass

    try:
        provider = get_provider(account.platform, credentials)
    except ValueError:
        logger.error("Health check: no provider for platform %s", account.platform)
        return

    # Enable auto-refresh on 401 as a safety net for all API calls.
    # For FB/IG/Threads pages: use the page access token (account.oauth_access_token)
    # for fb_exchange_token, NOT the user-level token stored in oauth_refresh_token.
    if account.platform in ("facebook", "instagram", "instagram_login", "threads"):
        refresh_token = account.oauth_access_token
    else:
        refresh_token = account.oauth_refresh_token
    provider.set_refresh_token(refresh_token)

    # Bluesky accounts connected before we recorded token_expires_at need a
    # one-shot refresh to populate it; without this, is_token_expiring_soon
    # stays False forever and the short-lived accessJwt is never rotated.
    needs_bluesky_bootstrap = account.platform == "bluesky" and account.token_expires_at is None
    if account.is_token_expiring_soon or needs_bluesky_bootstrap:
        # For FB/IG/Threads pages: use the page access token for fb_exchange_token.
        # oauth_refresh_token is a user-level token placeholder, not a page-level token.
        if account.platform in ("facebook", "instagram", "instagram_login", "threads"):
            refresh_token = account.oauth_access_token
        else:
            refresh_token = account.oauth_refresh_token
        # LinkedIn Personal OIDC mode doesn't issue refresh tokens (~60 day expiry)
        if not refresh_token and account.platform == "linkedin_personal" and account.is_token_expiring_soon:
            account.connection_status = SocialAccount.ConnectionStatus.TOKEN_EXPIRING
            account.last_error = "LinkedIn OIDC tokens expire after ~60 days. Please reconnect your account."
            account.save(
                update_fields=["connection_status", "last_error", "updated_at"]
            )
            logger.warning("LinkedIn Personal OIDC token expired for %s, reconnect required", account)
        elif refresh_token:
            try:
                new_tokens = provider.refresh_token(refresh_token)
                account.oauth_access_token = new_tokens.access_token
                if new_tokens.refresh_token:
                    account.oauth_refresh_token = new_tokens.refresh_token
                if new_tokens.expires_in:
                    account.token_expires_at = timezone.now() + timedelta(seconds=new_tokens.expires_in)
                account.connection_status = SocialAccount.ConnectionStatus.CONNECTED
                account.last_error = ""
                logger.info("Health check: refreshed token for %s", account)
            except Exception as e:
                logger.warning("Health check: token refresh failed for %s: %s", account, e)
                account.connection_status = SocialAccount.ConnectionStatus.TOKEN_EXPIRING
                account.last_error = friendly_health_check_error(e)

    # Validate token by fetching profile
    # Skip profile fetch when refresh just set TOKEN_EXPIRING — we already
    # know the token is bad and don't want to overwrite with a generic ERROR.
    if account.connection_status != SocialAccount.ConnectionStatus.TOKEN_EXPIRING:
        try:
            profile = provider.get_profile(account.oauth_access_token)
            # Persist tokens if auto-refresh happened during the profile fetch
            refreshed = provider.get_last_refreshed_tokens()
            if refreshed:
                account.oauth_access_token = refreshed.access_token
                if refreshed.refresh_token:
                    account.oauth_refresh_token = refreshed.refresh_token
                if refreshed.expires_in:
                    account.token_expires_at = timezone.now() + timedelta(seconds=refreshed.expires_in)
            account.follower_count = profile.follower_count
            # Provider CDNs (TikTok, Meta) return signed avatar URLs that
            # expire; display names and handles can also change on-platform.
            # Guard each write so a transient empty response doesn't wipe
            # previously-good values.
            if profile.avatar_url:
                account.avatar_url = profile.avatar_url
            if profile.name:
                account.account_name = profile.name
            if profile.handle:
                account.account_handle = profile.handle
            if account.connection_status != SocialAccount.ConnectionStatus.TOKEN_EXPIRING:
                account.connection_status = SocialAccount.ConnectionStatus.CONNECTED
            account.last_error = ""
        except Exception as e:
            logger.warning("Health check: profile fetch failed for %s: %s", account, e)
            account.connection_status = SocialAccount.ConnectionStatus.ERROR
            account.last_error = friendly_health_check_error(e)

    account.last_health_check_at = timezone.now()
    account.save(
        update_fields=[
            "oauth_access_token",
            "oauth_refresh_token",
            "token_expires_at",
            "follower_count",
            "avatar_url",
            "account_name",
            "account_handle",
            "connection_status",
            "last_error",
            "last_health_check_at",
            "updated_at",
        ]
    )


@background(schedule=0)
def schedule_all_health_checks():
    """Enqueue individual health checks for all active accounts."""
    from .models import SocialAccount

    accounts = SocialAccount.objects.filter(
        connection_status__in=[
            SocialAccount.ConnectionStatus.CONNECTED,
            SocialAccount.ConnectionStatus.TOKEN_EXPIRING,
        ]
    ).values_list("id", flat=True)

    count = 0
    for account_id in accounts:
        check_social_account_health(str(account_id))
        count += 1

    logger.info("Scheduled health checks for %d accounts", count)
