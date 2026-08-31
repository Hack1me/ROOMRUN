from django.contrib import admin

from .models import MaintenanceRequest
from .models import Task

admin.site.register([MaintenanceRequest, Task])
