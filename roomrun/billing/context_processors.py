from billing.views import landlord_wallet_balance


def landlord_wallet(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not hasattr(user, "landlord_profile"):
        return {}
    return {"landlord_wallet_balance": landlord_wallet_balance(user.landlord_profile)}
