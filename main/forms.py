from dataclasses import field
from django.forms import ModelForm, Form
from .models import Item
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox
from daugia.settings import RECAPTCHA_PUBLIC_KEY, RECAPTCHA_PRIVATE_KEY

class ItemImgForm(ModelForm):
    class Meta:
        model = Item
        fields = ['img']

class FormWithCaptcha(Form):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox,
        public_key=RECAPTCHA_PUBLIC_KEY,
        private_key=RECAPTCHA_PRIVATE_KEY,
    )