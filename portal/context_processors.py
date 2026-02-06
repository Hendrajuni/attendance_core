from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        # Get unread notifications
        all_notifs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
        unread_count = all_notifs.filter(is_read=False).count()
        latest_notifs = all_notifs[:5]
        
        return {
            'unread_notifications_count': unread_count,
            'latest_notifications': latest_notifs,
        }
    return {
        'unread_notifications_count': 0,
        'latest_notifications': [],
    }
