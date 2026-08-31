from django.contrib import admin

from .models import Building
from .models import Property
from .models import PropertyImage
from .models import Unit

admin.site.register([Property, PropertyImage, Building, Unit])
