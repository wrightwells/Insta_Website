from django import forms
from django.utils.translation import gettext_lazy as _


class EnquiryForm(forms.Form):
    email = forms.EmailField(max_length=254, label=_("Email address"),
        widget=forms.EmailInput(attrs={'autocomplete':'email'}))
    mobile = forms.RegexField(regex=r'^[+0-9().\s-]{7,40}$', max_length=40,
        label=_("Mobile number"), widget=forms.TextInput(attrs={'type':'tel', 'autocomplete':'tel'}),
        error_messages={'invalid':_('Enter a valid mobile number, including the country code where needed.')})
    message = forms.CharField(max_length=5000, label=_("Message"), widget=forms.Textarea(attrs={'rows':7}))
    submission_token = forms.CharField(max_length=1024, widget=forms.HiddenInput)
    website = forms.CharField(required=False, max_length=200, label=_("Leave this field blank"),
        widget=forms.TextInput(attrs={'tabindex':'-1', 'autocomplete':'off'}))

    def clean_mobile(self):
        value = self.cleaned_data['mobile']
        if sum(char.isdigit() for char in value) < 7:
            raise forms.ValidationError(_('Enter a valid mobile number, including the country code where needed.'))
        return value
