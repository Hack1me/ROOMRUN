from django.views.generic import TemplateView


class LegalView(TemplateView):
    active_legal = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_legal"] = self.active_legal or self.request.resolver_match.url_name
        return context
