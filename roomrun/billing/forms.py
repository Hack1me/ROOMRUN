from billing.models import Charge
from core.utils.enums import ChargeType
from core.utils.enums import ContractStatus
from django import forms
from django.utils.translation import gettext_lazy as _
from rentals.models import RentalContract

LANDLORD_CHARGE_TYPES = tuple(
    (value, label)
    for value, label in ChargeType.choices
    if value not in {ChargeType.INITIAL_PAYMENT, ChargeType.CONTRACT_EXTENSION}
)


class LandlordChargeForm(forms.ModelForm):
    amount = forms.DecimalField(
        min_value=1,
        decimal_places=2,
        label=_("Amount (FCFA)"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "min": "1", "step": "1"}
        ),
    )

    class Meta:
        model = Charge
        fields = ("contract", "charge_type", "amount", "due_date", "description")
        widgets = {
            "contract": forms.Select(attrs={"class": "form-select"}),
            "charge_type": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4}
            ),
        }

    def __init__(self, *args, landlord, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract"].queryset = (
            RentalContract.landlord_objects.for_landlord(landlord)
            .filter(status=ContractStatus.ACTIVE)
            .select_related("tenant__user", "unit__building")
        )
        self.fields["contract"].label_from_instance = self._contract_label
        self.fields["charge_type"].choices = LANDLORD_CHARGE_TYPES
        self.fields["contract"].label = _("Active rental contract")
        self.fields["description"].required = False

    @staticmethod
    def _contract_label(contract):
        return _("%(tenant)s · %(unit)s · %(contract)s") % {
            "tenant": contract.tenant.user.full_name,
            "unit": contract.unit,
            "contract": contract.contract_number,
        }
