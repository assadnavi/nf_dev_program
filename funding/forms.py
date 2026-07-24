import os

from django import forms

from .site_text import get_text

PROPOSAL_EXTENSIONS = {'.pdf', '.doc', '.docx'}
INVOICE_EXTENSIONS = {'.pdf'}


class ApplicationForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    proposal = forms.FileField(
        label=get_text('forms.proposal_label'),
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
    )

    def clean_proposal(self):
        uploaded_file = self.cleaned_data['proposal']
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in PROPOSAL_EXTENSIONS:
            raise forms.ValidationError(get_text('forms.proposal_error'))
        return uploaded_file


class InvoiceUploadForm(forms.Form):
    invoice = forms.FileField(
        label=get_text('forms.invoice_label'),
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
    )

    def clean_invoice(self):
        uploaded_file = self.cleaned_data['invoice']
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in INVOICE_EXTENSIONS:
            raise forms.ValidationError(get_text('forms.invoice_error'))
        return uploaded_file


class ProgramForm(forms.Form):
    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))
    deadline = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text=get_text('program_form.deadline_help'),
    )


class DecisionForm(forms.Form):
    comment = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        required=False,
        label=get_text('forms.comment_label'),
    )
