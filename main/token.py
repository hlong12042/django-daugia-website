from ast import Pass
from django.contrib.auth.tokens import PasswordResetTokenGenerator
import six
from .models import Account

class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: Account, timestamp: int) -> str:
        return (
            six.text_type(user.pk) + six.text_type(timestamp) + six.text_type(user.is_verified)
        )

account_activation_token = AccountActivationTokenGenerator()