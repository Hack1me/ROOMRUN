import json
import logging

from billing.services.payment_service import PaymentService
from billing.services.payment_service import PaymentServiceError
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class CamPayWebhookView(View):
    """
    Webhook endpoint for CamPay notifications.

    Always returns 200 OK, even on errors, to prevent CamPay from
    retrying indefinitely. Errors are logged and handled internally.
    """

    def post(self, request, *args, **kwargs):
        # --- 1. Parse JSON ---
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("CamPay webhook: invalid payload")
            return HttpResponse(status=200)

        # --- 2. Extract reference ---
        transaction_reference = payload.get("reference")
        if not transaction_reference:
            logger.warning(
                "CamPay webhook: missing reference | payload=%s", payload
            )
            return HttpResponse(status=200)

        logger.info(
            "CamPay webhook received | ref=%s", transaction_reference
        )

        # --- 3. Process ---
        try:
            payment = PaymentService().handle_provider_notification(
                transaction_reference=transaction_reference,
            )
        except PaymentServiceError:
            logger.exception(
                "CamPay webhook: service error | ref=%s",
                transaction_reference,
            )
            return HttpResponse(status=200)
        except Exception:
            logger.exception(
                "CamPay webhook: unexpected error | ref=%s",
                transaction_reference,
            )
            return HttpResponse(status=200)

        # --- 4. Handle unknown reference ---
        if payment is None:
            logger.warning(
                "CamPay webhook: unknown reference | ref=%s",
                transaction_reference,
            )
            # Still 200 to stop retries.
            return HttpResponse(status=200)

        logger.info(
            "CamPay webhook processed | payment=%s | status=%s",
            payment.payment_number,
            payment.status,
        )
        return HttpResponse(status=200)
