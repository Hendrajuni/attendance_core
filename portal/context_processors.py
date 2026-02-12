from attendance.models import EmployeeProfile
from .models import Notification

def notifications(request):
    """
    Global context processor.
    Provides:
    - user_role: Current user's role (ACCOUNTING, HRD, KERANI, ADMIN/USER)
    - unread_notifications_count: Count of unread notifications
    - latest_notifications: 5 most recent notifications
    """
    context = {}
    
    # 1. Role Context
    if request.user.is_authenticated:
        try:
            profile = request.user.employee_profile
            context['user_role'] = profile.role
        except EmployeeProfile.DoesNotExist:
            context['user_role'] = 'ADMIN' if request.user.is_superuser else 'USER'
    else:
        context['user_role'] = 'GUEST'

    # 2. Notification Context
    if request.user.is_authenticated:
        # Get unread notifications
        all_notifs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
        unread_count = all_notifs.filter(is_read=False).count()
        latest_notifs = all_notifs[:5]
        
        context['unread_notifications_count'] = unread_count
        context['latest_notifications'] = latest_notifs
    else:
        context['unread_notifications_count'] = 0
        context['latest_notifications'] = []
        
    return context
