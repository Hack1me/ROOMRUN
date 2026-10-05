from communications.forms import StartConversationForm
from communications.models import Conversation
from communications.models import Notification
from communications.services import ConversationService
from core.utils.enums import ContractStatus
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.db.models import Max
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView
from rentals.models import RentalContract
from users.models import User


def contacts_for_user(user):
    """Return users who share a valid landlord/tenant/staff relationship."""
    contacts = User.objects.none()

    if hasattr(user, "landlord_profile"):
        landlord = user.landlord_profile
        contacts = User.objects.filter(
            Q(
                tenant_profile__rental_contracts__unit__building__property_ref__landlord=landlord
            )
            | Q(invitations__landlord=landlord, invitations__status="ACCEPTED")
            | Q(
                employee_profile__invitations__landlord=landlord,
                employee_profile__invitations__status="ACCEPTED",
            )
        )
    elif hasattr(user, "tenant_profile"):
        contacts = User.objects.filter(
            landlord_profile__properties__buildings__units__rental_contracts__tenant=user.tenant_profile
        )
    elif hasattr(user, "employee_profile") and hasattr(
        user.employee_profile, "guard_profile"
    ):
        landlords = user.employee_profile.guard_profile.landlords.all()
        contacts = User.objects.filter(
            Q(landlord_profile__in=landlords)
            | Q(
                tenant_profile__rental_contracts__unit__building__property_ref__landlord__in=landlords,
                tenant_profile__rental_contracts__status=ContractStatus.ACTIVE,
            )
        )

    elif hasattr(user, "employee_profile"):
        contacts = User.objects.filter(
            Q(
                invitations__employee=user.employee_profile,
                invitations__status="ACCEPTED",
            )
            | Q(invitations__user=user, invitations__status="ACCEPTED")
        ).values_list("invitations__landlord__user", flat=True)
        contacts = User.objects.filter(pk__in=contacts)

    return (
        contacts.exclude(pk=user.pk)
        .distinct()
        .order_by("first_name", "last_name", "email")
    )


def is_tenant_user(user):
    """Use the profile relation as the canonical role check."""
    return hasattr(user, "tenant_profile") and not hasattr(user, "landlord_profile")


def set_display_names(conversations, user):
    """Expose the other participant as the conversation name for this viewer."""
    for conversation in conversations:
        other_participant = next(
            (
                participant
                for participant in conversation.participants.all()
                if participant.pk != user.pk
            ),
            None,
        )
        conversation.display_name = (
            other_participant.full_name or other_participant.email
            if other_participant
            else conversation.title or _("Conversation")
        )
        conversation.display_avatar_url = (
            other_participant.profile_picture.url
            if other_participant and other_participant.profile_picture
            else ""
        )


def tenant_chat_context(user):
    """Provide the tenant's current home and landlord for the chat sidebar."""
    if not hasattr(user, "tenant_profile"):
        return {"is_tenant_chat": False}

    contract = (
        RentalContract.objects.filter(tenant=user.tenant_profile)
        .select_related("unit__building__property_ref__landlord__user")
        .order_by("-start_date", "-created_at")
        .first()
    )
    if not contract:
        return {
            "is_tenant_chat": True,
            "tenant_contract": None,
            "tenant_landlord": None,
        }

    return {
        "is_tenant_chat": True,
        "tenant_contract": contract,
        "tenant_landlord": contract.unit.building.property_ref.landlord,
    }


def guard_chat_context(user):
    return {
        "is_guard_chat": bool(
            hasattr(user, "employee_profile")
            and hasattr(user.employee_profile, "guard_profile")
        )
    }


def notification_role_context(user):
    is_tenant = hasattr(user, "tenant_profile") and not hasattr(
        user, "landlord_profile"
    )
    is_guard = hasattr(user, "employee_profile") and hasattr(
        user.employee_profile, "guard_profile"
    )
    is_maintenance = hasattr(user, "employee_profile") and hasattr(
        user.employee_profile, "maintenance_agent_profile"
    )
    return {
        "is_tenant_notifications": is_tenant,
        "is_guard_notifications": is_guard,
        "is_maintenance_notifications": is_maintenance,
        "is_landlord_notifications": not (is_tenant or is_guard or is_maintenance),
    }


class NotificationListView(LoginRequiredMixin, ListView):
    """Show only notifications belonging to the signed-in user."""

    model = Notification
    template_name = "communications/notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        unread = self.request.GET.get("status") == "unread"
        if unread:
            queryset = queryset.filter(is_read=False)
        return queryset.select_related("related_content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unread_notification_count"] = Notification.objects.filter(
            recipient=self.request.user, is_read=False
        ).count()
        context["unread_only"] = self.request.GET.get("status") == "unread"
        context.update(notification_role_context(self.request.user))
        return context


class NotificationDetailView(LoginRequiredMixin, DetailView):
    model = Notification
    template_name = "communications/notifications/detail.html"
    context_object_name = "notification"

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def get_object(self, queryset=None):
        notification = super().get_object(queryset)
        notification.mark_as_read()
        return notification

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(notification_role_context(self.request.user))
        return context


class NotificationOpenView(LoginRequiredMixin, View):
    """Mark a notification read and send the user to its related page."""

    def get(self, request, pk):
        notification = get_object_or_404(
            Notification.objects.select_related("related_content_type"),
            pk=pk,
            recipient=request.user,
        )
        notification.mark_as_read()
        target = notification_target_url(notification, request.user)
        return HttpResponseRedirect(
            target
            or reverse(
                "communications:notification-detail", kwargs={"pk": notification.slug}
            )
        )


def notification_target_url(notification, user):  # noqa: C901, PLR0911, PLR0912
    """Resolve a notification's related object to the appropriate user page."""
    related = notification.related_object
    if not related:
        return None
    is_tenant = hasattr(user, "tenant_profile") and not hasattr(
        user, "landlord_profile"
    )
    is_guard = hasattr(user, "employee_profile") and hasattr(
        user.employee_profile, "guard_profile"
    )
    if hasattr(related, "payment_number"):
        return (
            reverse("billing:tenant-payment-sync", kwargs={"pk": related.slug})
            if is_tenant
            else reverse("billing:landlord-wallet")
        )
    if hasattr(related, "charge_number"):
        return (
            reverse("billing:tenant-payment-initiate", kwargs={"pk": related.slug})
            if is_tenant
            else reverse("billing:landlord-charge-list")
        )
    if hasattr(related, "application_number"):
        route = (
            "rentals:rental-application-detail"
            if is_tenant
            else "rentals:landlord-rental-application-detail"
        )
        return reverse(route, kwargs={"pk": related.slug})
    if hasattr(related, "requested_end_date") and hasattr(related, "contract"):
        if is_tenant:
            return reverse("rentals:tenant-lease-detail")
        return reverse(
            "rentals:landlord-rental-contract-detail",
            kwargs={"pk": related.contract.slug},
        )
    if hasattr(related, "contract_number"):
        if is_tenant and related.status == "SIGNING":
            return reverse(
                "rentals:tenant-rental-contract-sign", kwargs={"pk": related.slug}
            )
        if is_tenant:
            return reverse("rentals:tenant-lease-detail")
        return reverse(
            "rentals:landlord-rental-contract-detail", kwargs={"pk": related.slug}
        )
    if hasattr(related, "request_number"):
        route = (
            "maintenance:request-detail"
            if is_tenant
            else "maintenance:landlord-request-detail"
        )
        return reverse(route, kwargs={"pk": related.slug})
    if hasattr(related, "task_number"):
        return reverse("maintenance:task-detail", kwargs={"pk": related.slug})
    if hasattr(related, "schedule_number"):
        return (
            reverse("operations:tenant-cleaning-list")
            if is_tenant
            else reverse("operations:cleaning-detail", kwargs={"pk": related.slug})
        )
    if hasattr(related, "visit_number"):
        route = (
            "operations:guard-visitors"
            if is_guard
            else "operations:visitor-invitations"
        )
        return reverse(route)
    if related.__class__.__name__ == "Conversation":
        return reverse(
            "communications:conversation-detail", kwargs={"pk": related.slug}
        )
    if hasattr(related, "get_absolute_url"):
        return related.get_absolute_url()
    return None


class NotificationToggleReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if notification.is_read:
            notification.mark_as_unread()
        else:
            notification.mark_as_read()
        return HttpResponseRedirect(reverse("communications:notification-list"))


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        messages.success(request, _("All notifications have been marked as read."))
        return HttpResponseRedirect(reverse("communications:notification-list"))


class NotificationDeleteView(LoginRequiredMixin, View):
    """Delete one notification belonging to the signed-in user."""

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user,
        )
        notification.delete()
        messages.success(request, _("Notification deleted."))
        return HttpResponseRedirect(reverse("communications:notification-list"))


class NotificationDeleteAllView(LoginRequiredMixin, View):
    """Clear the signed-in user's notification inbox."""

    def post(self, request):
        Notification.objects.filter(recipient=request.user).delete()
        messages.success(request, _("All notifications have been deleted."))
        return HttpResponseRedirect(reverse("communications:notification-list"))


def conversations_for_user(user):
    conversations = Conversation.objects.filter(participants=user)
    if hasattr(user, "employee_profile") and hasattr(
        user.employee_profile, "guard_profile"
    ):
        return conversations.filter(participants__in=contacts_for_user(user)).distinct()
    return conversations


class ConversationListView(LoginRequiredMixin, ListView):
    """
    List all conversations the authenticated user is a participant of.
    """

    template_name = "communications/conversations/list.html"
    context_object_name = "conversations"
    paginate_by = 20

    def get_template_names(self):
        if is_tenant_user(self.request.user):
            return ["communications/conversations/tenant_list.html"]
        return ["communications/conversations/list.html"]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            conversations_for_user(user)
            .filter(participants=user)
            .annotate(
                msg_count=Count("messages", distinct=True),
                last_msg=Max("messages__created_at"),
            )
            .prefetch_related("participants")
            .order_by("-last_message_at", "-created_at")
        )

        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(participants__first_name__icontains=query)
                | Q(participants__last_name__icontains=query)
                | Q(participants__email__icontains=query)
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Attach unread count per conversation.
        conversations = context["conversations"]
        for conv in conversations:
            conv.unread_count = ConversationService.unread_count(
                conversation=conv,
                user=self.request.user,
            )
        set_display_names(conversations, self.request.user)

        selected_id = self.request.GET.get("conversation")
        selected_conversation = None
        if selected_id:
            selected_conversation = next(
                (conv for conv in conversations if str(conv.pk) == selected_id),
                None,
            )
        if selected_conversation is None and conversations:
            selected_conversation = conversations[0]

        context["selected_conversation"] = selected_conversation
        context["start_conversation_form"] = StartConversationForm(
            contacts=contacts_for_user(self.request.user)
        )
        context.update(tenant_chat_context(self.request.user))
        context.update(guard_chat_context(self.request.user))
        if selected_conversation:
            context["chat_messages"] = list(
                selected_conversation.messages.select_related("sender").order_by(
                    "-created_at"
                )[:50][::-1]
            )
            context["other_participants"] = selected_conversation.participants.exclude(
                pk=self.request.user.pk
            )
        else:
            context["chat_messages"] = []
            context["other_participants"] = []

        return context


class ConversationDetailView(LoginRequiredMixin, DetailView):
    """
    Display a single conversation with its messages.
    """

    context_object_name = "conversation"

    def get_template_names(self):
        if is_tenant_user(self.request.user):
            return ["communications/conversations/tenant_list.html"]
        return ["communications/conversations/list.html"]

    def get_object(self, queryset=None):
        # Ensure the user is a participant.
        return get_object_or_404(
            conversations_for_user(self.request.user)
            .prefetch_related("participants")
            .filter(participants=self.request.user),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.object

        # Mark as read on open.
        ConversationService.mark_as_read(
            conversation=conversation,
            user=self.request.user,
        )

        conversations = list(
            conversations_for_user(self.request.user)
            .annotate(
                msg_count=Count("messages", distinct=True),
                last_msg=Max("messages__created_at"),
            )
            .prefetch_related("participants")
            .order_by("-last_message_at", "-created_at")
        )
        for item in conversations:
            item.unread_count = ConversationService.unread_count(
                conversation=item,
                user=self.request.user,
            )
        set_display_names(conversations, self.request.user)
        set_display_names([conversation], self.request.user)

        context["conversations"] = conversations
        context["selected_conversation"] = conversation
        context["start_conversation_form"] = StartConversationForm(
            contacts=contacts_for_user(self.request.user)
        )
        context.update(tenant_chat_context(self.request.user))
        context.update(guard_chat_context(self.request.user))
        context["chat_messages"] = list(
            conversation.messages.select_related("sender").order_by("-created_at")[:50][
                ::-1
            ]
        )
        context["other_participants"] = conversation.participants.exclude(
            pk=self.request.user.pk
        )

        return context


class StartConversationView(LoginRequiredMixin, View):
    """Create (or reopen) a direct conversation with an authorised contact."""

    def post(self, request, *args, **kwargs):
        form = StartConversationForm(
            request.POST,
            contacts=contacts_for_user(request.user),
        )
        if not form.is_valid():
            messages.error(request, _("Choose a contact from your workspace."))
            return HttpResponseRedirect(reverse("communications:conversation-list"))

        recipient = form.cleaned_data["recipient"]
        conversation, _created = ConversationService.get_or_create_direct_conversation(
            user=request.user,
            recipient=recipient,
        )

        return HttpResponseRedirect(
            f"{reverse('communications:conversation-list')}?conversation={conversation.pk}"
        )


class ConversationDeleteView(LoginRequiredMixin, View):
    """Permanently remove a conversation and its messages for all participants."""

    def post(self, request, *args, **kwargs):
        conversation = get_object_or_404(
            conversations_for_user(request.user),
            pk=kwargs["pk"],
        )
        conversation.delete()
        messages.success(request, _("The conversation was deleted."))
        return HttpResponseRedirect(reverse("communications:conversation-list"))
