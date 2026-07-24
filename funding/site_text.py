"""
Every piece of user-facing text on the site lives here — edit this file to
change wording anywhere on the site. The dev server picks up changes
automatically (Django's autoreloader watches every .py file).

Entries containing Django template syntax (e.g. "{{ program.name }}") are
rendered through Django's own template engine — against the current page's
context for template-side text, or against the keyword arguments passed to
render_text() for text assembled in Python (e.g. flash messages). This lets
these entries use exactly the same {{ variable }} syntax as the templates
themselves.
"""

from django.template import Context, Template

SITE_TEXT = {
    'site': {
        'brand': 'NF Dev Programmes',
    },
    'nav': {
        'logout': 'Log out',
    },
    'login': {
        'heading': 'Admin log in',
        'username_label': 'Username',
        'password_label': 'Password',
        'submit': 'Log in',
    },
    'program_list': {
        'page_title': 'Programmes',
        'new_button': 'New programme',
        'col_name': 'Name',
        'col_deadline': 'Deadline',
        'col_applications': 'Applications',
        'col_status': 'Status',
        'applications_total_suffix': 'total',
        'status_open': 'Open',
        'status_closed': 'Closed',
        'empty': 'No programmes yet.',
    },
    'program_form': {
        'page_title': 'New programme',
        'name_label': 'Name',
        'deadline_label': 'Deadline',
        'deadline_help': 'Applications close at 11:59pm on this date.',
        'submit': 'Create programme',
    },
    'program_detail': {
        'deadline_prefix': 'Deadline:',
        'status_open': 'Open for submissions',
        'status_closed': 'Closed for submissions',
        'link_card_title': 'Application link',
        'link_card_body': 'Share this link with applicants so they can submit to this programme:',
        'col_email': 'Email',
        'col_submitted': 'Submitted',
        'col_status': 'Status',
        'empty': 'No applications.',
    },
    'application_detail': {
        'documents_title': 'Documents',
        'proposal_label': 'Proposal:',
        'upfront_invoice_label': 'Upfront invoice:',
        'final_invoice_label': 'Final invoice:',
        'decision_title': 'Decision',
        'accept_button': 'Accept',
        'refuse_button': 'Refuse',
        'applicant_link_title': 'Applicant link',
        'applicant_link_body': 'Share this link with the applicant so they can upload the upfront invoice:',
        'approve_work_title': 'Approve work',
        'approve_work_body': (
            'The upfront invoice has been received. Once the funded work is confirmed done, '
            'approve it so the applicant can submit the final invoice.'
        ),
        'approve_work_button': 'Approve work',
        'waiting_final_invoice': 'Waiting on the applicant to submit the final invoice via their link:',
        'status_history_title': 'Status history',
    },
    'apply_form': {
        'page_title': 'Apply — {{ program.name }}',
        'deadline_notice': 'Applications close on {{ program.deadline }}.',
        'email_label': 'Email',
        'submit': 'Submit application',
    },
    'apply_closed': {
        'page_title': 'Applications closed',
        'message': 'Applications for this programme closed on {{ program.deadline }}.',
    },
    'apply_success': {
        'page_title': 'Application submitted',
        'heading': 'Thank you',
        'message': 'Your application to <strong>{{ program.name }}</strong> has been submitted.',
    },
    'application_status': {
        'page_title': 'Your application',
        'heading': 'Your application to {{ application.program.name }}',
        'refused': 'Unfortunately your application was not accepted.',
        'upfront_pending_notice': 'Your application has been accepted. Please upload your upfront invoice below.',
        'upfront_submit': 'Upload upfront invoice',
        'awaiting_approval_notice': (
            "Your upfront invoice has been received. We'll be in touch once the work is reviewed "
            "and approved — you'll then be able to submit your final invoice here."
        ),
        'final_pending_notice': 'The work has been approved. Please upload your final invoice below.',
        'final_submit': 'Upload final invoice',
        'complete_notice': 'Your final invoice has been received. This application is now complete — thank you.',
        'fallback_notice': 'Your application has been submitted and is awaiting review.',
    },
    'messages': {
        'program_created': 'Programme "{{ name }}" created and open for submissions.',
        'application_accepted': 'Application accepted.',
        'application_refused': 'Application refused.',
        'work_approved': 'Work approved — applicant can now submit the final invoice.',
        'unknown_action': 'Unknown action.',
    },
    'forms': {
        'proposal_label': 'Project proposal (PDF or Word document)',
        'proposal_error': 'The proposal must be a PDF or Word document (.pdf, .doc, .docx).',
        'invoice_label': 'Invoice (PDF)',
        'invoice_error': 'The invoice must be a PDF file (.pdf).',
        'comment_label': 'Comment (optional)',
    },
    'application_status_labels': {
        'submitted': 'Submitted',
        'refused': 'Refused',
        'upfront_invoice_pending': 'Accepted (Upfront Invoice Pending)',
        'awaiting_work_approval': 'Upfront Invoice Received (Awaiting Work Approval)',
        'final_invoice_pending': 'Work Approved (Final Invoice Pending)',
        'complete': 'Complete',
    },
    'status_history_labels': {
        'submitted': 'Submitted',
        'accepted': 'Accepted',
        'refused': 'Refused',
        'upfront_invoice_received': 'Upfront invoice received',
        'work_approved': 'Work approved',
        'final_invoice_received': 'Final invoice received (Complete)',
    },
    'errors': {
        'only_submitted_can_be_accepted': 'Only a submitted application can be accepted.',
        'only_submitted_can_be_refused': 'Only a submitted application can be refused.',
        'upfront_invoice_not_expected': 'Upfront invoice is not expected in the current status.',
        'work_approval_not_expected': 'Work approval is not expected in the current status.',
        'final_invoice_not_expected': 'Final invoice is not expected in the current status.',
        'unknown_document': 'Unknown document.',
        'document_not_uploaded_yet': 'This document has not been uploaded yet.',
    },
}


def get_text(key_path):
    """Look up a dotted key path, e.g. get_text('program_list.empty')."""
    node = SITE_TEXT
    for part in key_path.split('.'):
        node = node[part]
    return node


def render_text(key_path, **context_vars):
    """Render a SITE_TEXT entry that contains Django template syntax (e.g. {{ name }}),
    for use in Python code (e.g. flash messages) rather than inside a template."""
    return Template(get_text(key_path)).render(Context(context_vars))
