from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AccessLog

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
    AccessLog.objects.create(
        user=user,
        action='LOGIN',
        ip_address=ip,
        user_agent=user_agent,
        status='SUCCESS'
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
    AccessLog.objects.create(
        user=user,
        action='LOGOUT',
        ip_address=ip,
        user_agent=user_agent,
        status='SUCCESS'
    )

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
    # Attempt to find user by username, but don't crash if not found
    # credentials usually contains 'username'
    username = credentials.get('username')
    
    # We create a log without a user relation (since login failed), unless we want to look it up.
    # But AccessLog.user is FK to User. If user doesn't exist, we can't link it.
    # So we leave user null, and maybe put username in user_agent or another field?
    # For now, let's just log ip/agent.
    
    AccessLog.objects.create(
        user=None,
        action='LOGIN_FAILED',
        ip_address=ip,
        user_agent=f"{user_agent} | Username: {username}",
        status='FAILURE'
    )
