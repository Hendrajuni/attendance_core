import uuid
from django.db import models
from django.contrib.auth.models import User
from attendance.models import WorkLocation

class Notification(models.Model):
    """
    Sistem notifikasi sederhana untuk user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=255, null=True, blank=True, help_text="Link tujuan saat diklik")
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional filtering context
    related_location = models.ForeignKey(WorkLocation, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"
