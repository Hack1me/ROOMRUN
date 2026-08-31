from django.contrib import admin

from .models import Announcement
from .models import Message
from .models import Notification

admin.site.register([Announcement, Notification, Message])
