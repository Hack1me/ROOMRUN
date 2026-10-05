import hashlib
import hmac

from billing.services.gateways import verify_webhook_signature
from billing.services.wallet_service import validate_withdrawal_amount
from billing.views import CamPayWebhookView
from billing.views import DigiPayWebhookView
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.test import SimpleTestCase
from django.test import override_settings
from djmoney.money import Money


class WebhookSignatureTests(SimpleTestCase):
    @override_settings(
        CAMPAY_WEBHOOK_SECRET="campay-test-secret",  # noqa: S106
        DIGIPAY_WEBHOOK_SECRET="digipay-test-secret",  # noqa: S106
    )
    def test_accepts_valid_signatures_for_both_providers(self):
        body = b'{"reference":"tx-123"}'
        for provider, secret in (
            ("CAMPAY", "campay-test-secret"),
            ("DIGIPAY", "digipay-test-secret"),
        ):
            signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            with self.subTest(provider=provider):
                assert verify_webhook_signature(provider, body, signature)
                assert verify_webhook_signature(provider, body, f"sha256={signature}")

    @override_settings(CAMPAY_WEBHOOK_SECRET="configured-secret")  # noqa: S106
    def test_rejects_missing_invalid_or_modified_signatures(self):
        signature = hmac.new(
            b"configured-secret", b"original", hashlib.sha256
        ).hexdigest()
        assert not verify_webhook_signature("CAMPAY", b"original", "")
        assert not verify_webhook_signature("CAMPAY", b"modified", signature)
        assert not verify_webhook_signature("UNKNOWN", b"original", signature)

    @override_settings(CAMPAY_WEBHOOK_SECRET="configured-secret")  # noqa: S106
    def test_webhook_rejects_request_before_parsing_if_signature_is_missing(self):
        request = RequestFactory().post(
            "/billing/webhook/campay/",
            data=b"not-json",
            content_type="application/json",
        )
        response = CamPayWebhookView.as_view()(request)
        assert response.status_code == 401  # noqa: PLR2004

    @override_settings(DIGIPAY_WEBHOOK_SECRET="configured-secret")  # noqa: S106
    def test_webhook_accepts_signed_body_before_json_decode(self):
        body = b"not-json"
        signature = hmac.new(b"configured-secret", body, hashlib.sha256).hexdigest()
        request = RequestFactory().post(
            "/billing/webhook/digipay/",
            data=body,
            content_type="application/json",
            HTTP_X_DIGIPAY_SIGNATURE=f"sha256={signature}",
        )
        response = DigiPayWebhookView.as_view()(request)
        assert response.status_code == 200  # noqa: PLR2004


class WalletServiceTests(SimpleTestCase):
    def test_withdrawal_rejects_amount_over_available_balance(self):
        with self.assertRaisesMessage(
            ValidationError,
            "The requested amount exceeds your available balance.",
        ):
            validate_withdrawal_amount(5000, Money(0, "XAF"))
