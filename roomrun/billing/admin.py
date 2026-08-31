from django.contrib import admin

from .models import Charge
from .models import Payment
from .models import Receipt

admin.site.register([Charge, Payment, Receipt])
