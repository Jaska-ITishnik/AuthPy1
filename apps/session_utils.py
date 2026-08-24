from django.utils import timezone
from django.utils.crypto import salted_hmac


SESSION_IP_KEY = "auth_ip_address"
SESSION_LAST_ACTIVITY_KEY = "auth_last_activity"
SESSION_USER_AGENT_KEY = "auth_user_agent"


def record_session_activity(request):
    """Persist lightweight device metadata in the authenticated session."""
    request.session[SESSION_IP_KEY] = request.META.get("REMOTE_ADDR", "")[:45]
    request.session[SESSION_USER_AGENT_KEY] = request.META.get("HTTP_USER_AGENT", "")[:500]
    request.session[SESSION_LAST_ACTIVITY_KEY] = timezone.now().isoformat()


def describe_user_agent(user_agent):
    value = user_agent.lower()

    if "edg/" in value:
        browser = "Edge"
    elif "opr/" in value or "opera" in value:
        browser = "Opera"
    elif "chrome/" in value or "crios/" in value:
        browser = "Chrome"
    elif "firefox/" in value or "fxios/" in value:
        browser = "Firefox"
    elif "safari/" in value:
        browser = "Safari"
    else:
        browser = "Noma’lum brauzer"

    if "iphone" in value or "ipad" in value:
        operating_system = "iOS"
    elif "android" in value:
        operating_system = "Android"
    elif "windows" in value:
        operating_system = "Windows"
    elif "macintosh" in value or "mac os" in value:
        operating_system = "macOS"
    elif "ubuntu" in value:
        operating_system = "Ubuntu"
    elif "linux" in value:
        operating_system = "Linux"
    else:
        operating_system = "Noma’lum qurilma"

    return f"{browser} · {operating_system}"


def make_session_revoke_token(user_id, session_key):
    """Create a non-reversible identifier without exposing the session key."""
    value = f"{user_id}:{session_key}"
    return salted_hmac("apps.session-revoke", value).hexdigest()
