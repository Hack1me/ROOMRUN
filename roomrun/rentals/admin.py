from django.contrib import admin

from .models import ContractExtensionRequest
from .models import RentalApplication
from .models import RentalContract

admin.site.register([RentalApplication, RentalContract, ContractExtensionRequest])
