from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from users.forms import ProfileForm
from users.services import ProfileService


class ProfileView(LoginRequiredMixin, View):
    """
    View for displaying and updating the authenticated user's profile.

    Supports both standard form submissions and AJAX requests.
    - GET: renders the profile form with current user data.
    - POST: validates and updates the profile, returning either a
      redirect (standard) or a JSON response (AJAX).
    """

    template_name = "dashboard/pages/profile.html"

    def get(self, request):
        """Render the profile edit form with the current user's data."""
        profile_user = get_user_model().objects.get(pk=request.user.pk)
        form = ProfileForm(instance=profile_user)
        return render(
            request,
            self.template_name,
            {
                "profile_user": profile_user,
                "form": form,
            },
        )

    def post(self, request):
        """
        Process the profile update form submission.

        Handles both standard POST requests and AJAX requests.
        On success:
            - Standard: redirects to the profile page with a success message.
            - AJAX: returns a JSON response with success flag and user data.
        On validation error:
            - Standard: re-renders the form with errors.
            - AJAX: returns a JSON error response with field errors.
        On unexpected exception:
            - Standard: shows an error message and re-renders the form.
            - AJAX: returns a JSON error response with a generic message.
        """
        profile_user = get_user_model().objects.get(pk=request.user.pk)
        form = ProfileForm(
            request.POST,
            request.FILES,
            instance=profile_user,
        )

        # Detect AJAX requests via the X-Requested-With header.
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # --- Form validation ---
        if not form.is_valid():
            if is_ajax:
                return JsonResponse(
                    {"success": False, "errors": form.errors},
                    status=400,
                )
            return render(
                request,
                self.template_name,
                {
                    "profile_user": profile_user,
                    "form": form,
                },
            )

        # --- Update profile within a transaction ---
        try:
            with transaction.atomic():
                # ModelForm applies cleaned values to its instance during
                # validation. Reload the user so the service can compare the
                # submitted values with the values persisted in the database.
                profile_user = ProfileService.update(
                    get_user_model().objects.get(pk=request.user.pk),
                    form.cleaned_data,
                )
        except Exception:  # noqa: BLE001
            if is_ajax:
                return JsonResponse(
                    {
                        "success": False,
                        "errors": {
                            "__all__": _(
                                "An error occurred while updating your profile."
                            )
                        },
                    },
                    status=500,
                )
            messages.error(
                request,
                _("An error occurred while updating your profile."),
            )
            return render(
                request,
                self.template_name,
                {
                    "profile_user": profile_user,
                    "form": form,
                },
            )

        # --- Success ---
        if is_ajax:
            return JsonResponse(
                {
                    "success": True,
                    "message": str(_("Your profile has been updated successfully.")),
                    "user_data": {
                        "first_name": profile_user.first_name,
                        "last_name": profile_user.last_name,
                        "email": profile_user.email,
                        # Add other fields if needed (e.g., avatar URL)
                    },
                }
            )

        # Standard (non-AJAX) response: success message and redirect
        messages.success(
            request,
            _("Your profile has been updated successfully."),
        )
        return redirect("users:profile")
