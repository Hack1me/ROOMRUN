from communications.forms import StartConversationForm
from communications.models import Conversation
from communications.services import ConversationService
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.db.models import Max
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
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
            Conversation.objects
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
        if selected_conversation:
            context["chat_messages"] = list(
                selected_conversation.messages.select_related("sender")
                .order_by("-created_at")[:50][::-1]
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
            Conversation.objects
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
            Conversation.objects.filter(participants=self.request.user)
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
        context["chat_messages"] = list(
            conversation.messages.select_related("sender").order_by("-created_at")[:50][::-1]
        )
        context["other_participants"] = (
            conversation.participants
            .exclude(pk=self.request.user.pk)
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
            Conversation.objects.filter(participants=request.user),
            pk=kwargs["pk"],
        )
        conversation.delete()
        messages.success(request, _("The conversation was deleted."))
        return HttpResponseRedirect(reverse("communications:conversation-list"))
