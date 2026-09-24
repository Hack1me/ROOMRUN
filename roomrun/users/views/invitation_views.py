from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView
from operations.models import UserInvitation
from properties.mixins import LandlordRequiredMixin
from users.forms import LandlordInvitationForm
from users.forms import TenantInvitationAcceptForm
from users.services import InvitationAcceptanceService
from users.services import UserInvitationService
from utils.email import EmailUtil
from utils.enums import InvitationStatus


class LandlordInvitationListView(LandlordRequiredMixin, FormView):
    template_name = "dashboard/invitations/list.html"
    form_class = LandlordInvitationForm

    def get_queryset(self):
        return UserInvitation.objects.filter(invited_by=self.request.user).order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invitations"] = self.get_queryset()
        return context

    def form_valid(self, form):
        invitation, token = UserInvitationService.create(
            email=form.cleaned_data["email"],
            invited_by=self.request.user,
            role=form.cleaned_data["role"],
        )
        accept_url = self.request.build_absolute_uri(
            reverse("users:invitation-accept", kwargs={"token": token})
        )
        delivered = EmailUtil.send_email_with_template(
            template="emails/invitations/user_invitation.html",
            context={"invitation": invitation, "accept_url": accept_url, "landlord": self.get_landlord()},
            receivers=[invitation.email],
            subject=_("You are invited to ROOMRUN"),
        )
        if delivered:
            messages.success(self.request, _("Invitation sent successfully."))
        else:
            messages.warning(self.request, _("Invitation created, but the email could not be delivered."))
        return redirect("dashboard:invitation-list")


class LandlordInvitationCancelView(LandlordRequiredMixin, View):
    def post(self, request, pk):
        invitation = UserInvitation.objects.filter(
            pk=pk, invited_by=request.user, status=InvitationStatus.PENDING
        ).first()
        if invitation is None:
            raise Http404
        UserInvitationService.cancel(invitation)
        messages.success(request, _("Invitation cancelled."))
        return redirect("dashboard:invitation-list")


class InvitationAcceptView(FormView):
    template_name = "home/pages/auth/invitation_accept.html"
    form_class = TenantInvitationAcceptForm

    def dispatch(self, request, *args, **kwargs):
        try:
            self.invitation = UserInvitationService.get_by_token(kwargs["token"])
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("users:signin")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invitation"] = self.invitation
        return context

    def form_valid(self, form):
        try:
            user = InvitationAcceptanceService.accept(
                invitation=self.invitation,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                password=form.cleaned_data["password"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        login(self.request, user)
        messages.success(self.request, _("Your account is ready."))
        return redirect("dashboard:dashboard")

