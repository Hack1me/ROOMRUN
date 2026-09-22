from django import forms
from django.utils.translation import gettext_lazy as _


class StartConversationForm(forms.Form):
    """Select one authorised contact for a direct conversation."""

    recipient = forms.ModelChoiceField(
        queryset=None,
        empty_label=_("Choose a contact"),
        label=_("Contact"),
    )

    def __init__(self, *args, contacts, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["recipient"].queryset = contacts
