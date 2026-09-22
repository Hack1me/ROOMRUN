from communications.models import Conversation
from communications.services import ConversationService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.db.models import Max
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from django.views.generic import ListView


class ConversationListView(LoginRequiredMixin, ListView):
    """
    List all conversations the authenticated user is a participant of.
    """
    template_name = "communications/conversations/list.html"
    context_object_name = "conversations"
    paginate_by = 20

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
    template_name = "communications/conversations/list.html"
    context_object_name = "conversation"

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

        context["conversations"] = conversations
        context["selected_conversation"] = conversation
        context["chat_messages"] = list(
            conversation.messages.select_related("sender").order_by("-created_at")[:50][::-1]
        )
        context["other_participants"] = (
            conversation.participants
            .exclude(pk=self.request.user.pk)
        )

        return context
