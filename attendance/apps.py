from django.apps import AppConfig


class AttendanceCoreConfig(AppConfig):
    name = 'attendance'

    def ready(self):
        import attendance.signals
