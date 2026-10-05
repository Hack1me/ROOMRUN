from django.contrib import admin

from .models import Charge
from .models import Payment
from .models import Receipt
from .models import Withdrawal

admin.site.register([Charge, Payment, Receipt, Withdrawal])
