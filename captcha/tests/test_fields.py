import os
import uuid
import warnings

try:
    from unittest.mock import patch, PropertyMock, MagicMock
except ImportError:
    from mock import patch, PropertyMock, MagicMock

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from captcha import fields, widgets, constants
from captcha.client import RecaptchaResponse
from captcha._compat import HTTPError


class DefaultForm(forms.Form):
    captcha = fields.ReCaptchaField()


class TestFields(TestCase):

    @patch("captcha.fields.client.submit")
    def test_client_success_response(self, mocked_submit):
        mocked_submit.return_value = RecaptchaResponse(is_valid=True)
        form_params = {"g-recaptcha-response": "PASSED"}
        form = DefaultForm(form_params)
        self.assertTrue(form.is_valid())

    @patch("captcha.fields.client.submit")
    def test_client_failure_response(self, mocked_submit):
        mocked_submit.return_value = RecaptchaResponse(
            is_valid=False, error_codes=["410"]
        )
        form_params = {"g-recaptcha-response": "PASSED"}
        form = DefaultForm(form_params)
        self.assertFalse(form.is_valid())

    def test_widget_check(self):
        with self.assertRaises(ImproperlyConfigured):
            class ImporperForm(forms.Form):
                captcha = fields.ReCaptchaField(widget=forms.Textarea)

    @patch("captcha.fields.client.submit")
    def test_field_instantiate_values(self, mocked_submit):
        mocked_submit.return_value = RecaptchaResponse(is_valid=True)

        class NonDefaultForm(forms.Form):
            captcha = fields.ReCaptchaField(
                private_key="NewUpdatedKey", public_key="NewPubKey"
            )

        form_params = {"g-recaptcha-response": "PASSED"}
        form = NonDefaultForm(form_params)
        self.assertTrue(form.is_valid())
        mocked_submit.assert_called_with(
            private_key="NewUpdatedKey",
            recaptcha_response="PASSED",
            remoteip=None,
        )
        html = form.as_p()
        self.assertIn('data-sitekey="NewPubKey"', html)

    @patch("captcha.client.recaptcha_request")
    def test_field_captcha_errors(self, mocked_response):
        read_mock = MagicMock()
        read_mock.read.return_value = b'{"success": false, "error-codes":' \
            b'["invalid-input-response", "invalid-input-secret"]}'
        mocked_response.return_value = read_mock
        form_params = {"g-recaptcha-response": "PASSED"}
        form = DefaultForm(form_params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["captcha"],
            ["Error verifying reCAPTCHA, please try again."]
        )

        mocked_response.side_effect = HTTPError(
            url="https://www.google.com/recaptcha/api/siteverify",
            code=410,
            fp=None,
            msg="Oops",
            hdrs=""
        )
        form = DefaultForm(form_params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["captcha"],
            ["Error verifying reCAPTCHA, please try again."]
        )

    @override_settings(RECAPTCHA_PRIVATE_KEY=constants.TEST_PRIVATE_KEY)
    def test_test_key_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            class ImporperForm(forms.Form):
                captcha = fields.ReCaptchaField()

            assert len(w) == 1
            assert issubclass(w[-1].category, RuntimeWarning)
            assert "RECAPTCHA_PRIVATE_KEY or RECAPTCHA_PUBLIC_KEY" in str(
                w[-1].message)


class TestWidgets(TestCase):
    @patch("captcha.widgets.uuid.UUID.hex", new_callable=PropertyMock)
    def test_default_v2_checkbox_html(self, mocked_uuid):
        test_hex = "928e8e017b114e1b9d3a3e877cfc5844"
        mocked_uuid.return_value = test_hex

        class DefaultCheckForm(forms.Form):
            captcha = fields.ReCaptchaField()

        form = DefaultCheckForm()
        html = form.as_p()
        self.assertIn(
            '<script src="https://www.google.com/recaptcha/api.js'
            '?hl=en"></script>',
            html
        )
        self.assertIn('data-size="normal"', html)
        self.assertIn('class="g-recaptcha"', html)
        self.assertIn('data-callback="onSubmit_%s"' % test_hex, html)
        self.assertIn('required="True"', html)
        self.assertIn('data-widget-uuid="%s"' % test_hex, html)
        self.assertIn('data-sitekey="pubkey"', html)
        self.assertIn("var onSubmit_%s = function(token) {" % test_hex, html)

    @patch("captcha.widgets.uuid.UUID.hex", new_callable=PropertyMock)
    def test_v2_checkbox_attribute_changes_html(self, mocked_uuid):
        test_hex = "e83ccae286ad4784bd47f7ddc40cfd6f"
        mocked_uuid.return_value = test_hex

        class CheckboxAttrForm(forms.Form):
            captcha = fields.ReCaptchaField(
                widget=widgets.ReCaptchaV2Checkbox(
                    attrs={
                        "data-theme": "dark",
                        "language": "af",
                        "data-callback": "customCallback",
                        "data-size": "compact"
                    }
                )
            )

        form = CheckboxAttrForm()
        html = form.as_p()
        self.assertIn(
            '<script src="https://www.google.com/recaptcha/api.js'
            '?hl=af"></script>',
            html
        )
        self.assertIn('data-theme="dark"', html)
        self.assertNotIn('data-callback="onSubmit_%s"' % test_hex, html)
        self.assertIn('data-callback="customCallback"', html)
        self.assertIn('data-size="compact"', html)
        self.assertIn('class="g-recaptcha"', html)
        self.assertIn('required="True"', html)
        self.assertIn('data-widget-uuid="%s"' % test_hex, html)
        self.assertIn('data-sitekey="pubkey"', html)
        self.assertIn("var onSubmit_%s = function(token) {" % test_hex, html)

    @patch("captcha.widgets.uuid.UUID.hex", new_callable=PropertyMock)
    def test_default_v2_invisible_html(self, mocked_uuid):
        test_hex = "72f853eb8b7e4022b808be0f5c3bc297"
        mocked_uuid.return_value = test_hex

        class InvisForm(forms.Form):
            captcha = fields.ReCaptchaField(
                widget=widgets.ReCaptchaV2Invisible()
            )

        form = InvisForm()
        html = form.as_p()
        self.assertIn(
            '<script src="https://www.google.com/recaptcha/api.js'
            '?hl=en"></script>',
            html
        )
        self.assertIn('data-size="invisible"', html)
        self.assertIn('data-callback="onSubmit_%s"' % test_hex, html)
        self.assertIn('class="g-recaptcha"', html)
        self.assertIn('required="True"', html)
        self.assertIn('data-widget-uuid="%s"' % test_hex, html)
        self.assertIn('data-sitekey="pubkey"', html)
        self.assertIn("var onSubmit_%s = function(token) {" % test_hex, html)
        self.assertIn("var verifyCaptcha_%s = function(e) {" % test_hex, html)
        self.assertIn('.g-recaptcha[data-widget-uuid="%s"]' % test_hex, html)

    @patch("captcha.widgets.uuid.UUID.hex", new_callable=PropertyMock)
    def test_v2_invisible_attribute_changes_html(self, mocked_uuid):
        test_hex = "8b220c54ddb849b8bb59bda5da57baea"
        mocked_uuid.return_value = test_hex

        class InvisAttrForm(forms.Form):
            captcha = fields.ReCaptchaField(
                widget=widgets.ReCaptchaV2Invisible(
                    attrs={
                        "data-theme": "dark",
                        "language": "cl",
                        "data-callback": "customCallbackInvis",
                        "data-size": "compact"
                    }
                )
            )

        form = InvisAttrForm()
        html = form.as_p()
        self.assertIn(
            '<script src="https://www.google.com/recaptcha/api.js'
            '?hl=cl"></script>',
            html
        )
        self.assertNotIn('data-size="compact"', html)
        self.assertIn('data-size="invisible"', html)
        self.assertNotIn('data-callback="onSubmit_%s"' % test_hex, html)
        self.assertIn('data-callback="customCallbackInvis"', html)
        self.assertIn('class="g-recaptcha"', html)
        self.assertIn('required="True"', html)
        self.assertIn('data-widget-uuid="%s"' % test_hex, html)
        self.assertIn('data-sitekey="pubkey"', html)
        self.assertIn("var onSubmit_%s = function(token) {" % test_hex, html)
        self.assertIn("var verifyCaptcha_%s = function(e) {" % test_hex, html)
        self.assertIn('.g-recaptcha[data-widget-uuid="%s"]' % test_hex, html)