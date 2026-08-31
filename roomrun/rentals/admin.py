from django.contrib import admin

from .models import RentalApplication
from .models import RentalContract

admin.site.register([RentalApplication, RentalContract])
