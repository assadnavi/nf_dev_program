import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ApplicationForm, DecisionForm, InvoiceUploadForm, ProgramForm
from .models import Application, Program
from .site_text import get_text, render_text

# ---------------------------------------------------------------------------
# Public applicant views — no authentication, per design.md §4
# ---------------------------------------------------------------------------


def apply(request, program_id):
    program = get_object_or_404(Program, pk=program_id)

    if not program.is_open_for_submissions():
        return render(request, 'funding/apply_closed.html', {'program': program})

    if request.method == 'POST':
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            proposal = form.cleaned_data['proposal']
            Application.objects.create(
                program=program,
                email=form.cleaned_data['email'],
                proposal_filename=proposal.name,
                proposal_mimetype=proposal.content_type or 'application/octet-stream',
                proposal_blob=proposal.read(),
            )
            return render(request, 'funding/apply_success.html', {'program': program})
    else:
        form = ApplicationForm()

    return render(request, 'funding/apply_form.html', {'program': program, 'form': form})


def application_status(request, token):
    application = get_object_or_404(Application, access_token=token)
    status = application.status
    upload_form = None

    if status in ('upfront_invoice_pending', 'final_invoice_pending'):
        if request.method == 'POST':
            upload_form = InvoiceUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                uploaded_file = upload_form.cleaned_data['invoice']
                if status == 'upfront_invoice_pending':
                    application.receive_upfront_invoice(
                        uploaded_file.name,
                        uploaded_file.content_type or 'application/pdf',
                        uploaded_file.read(),
                    )
                else:
                    application.receive_final_invoice(
                        uploaded_file.name,
                        uploaded_file.content_type or 'application/pdf',
                        uploaded_file.read(),
                    )
                return redirect('application_status', token=token)
        else:
            upload_form = InvoiceUploadForm()

    return render(request, 'funding/application_status.html', {
        'application': application,
        'upload_form': upload_form,
    })


# ---------------------------------------------------------------------------
# Admin dashboard views — session-authenticated, per design.md §5
# ---------------------------------------------------------------------------

APPLICATION_DOCUMENT_FIELDS = {
    'proposal': ('proposal_filename', 'proposal_mimetype', 'proposal_blob'),
    'upfront_invoice': ('upfront_invoice_filename', 'upfront_invoice_mimetype', 'upfront_invoice_blob'),
    'final_invoice': ('final_invoice_filename', 'final_invoice_mimetype', 'final_invoice_blob'),
}


PROGRAM_LIST_COLUMNS = [
    ('name', get_text('program_list.col_name'), lambda p: p.name.lower()),
    ('deadline', get_text('program_list.col_deadline'), lambda p: p.deadline),
    ('applications', get_text('program_list.col_applications'), lambda p: p.total_applications),
    ('status', get_text('program_list.col_status'), lambda p: p.is_open_for_submissions()),
]

APPLICATION_LIST_COLUMNS = [
    ('email', get_text('program_detail.col_email'), lambda a: a.email.lower()),
    ('submitted', get_text('program_detail.col_submitted'), lambda a: a.submitted_at),
    ('status', get_text('program_detail.col_status'), lambda a: a.status_label.lower()),
]


def _sort_and_build_columns(request, items, column_defs):
    """Sort items in place per ?sort=&dir= and build column header info for the template.

    See design.md: sorting is applied in Python on the already-fetched list, since
    scale is tiny (a handful of programs/applications) and this keeps the sortable
    fields (some computed, some DB columns) handled uniformly.
    """
    current_sort = request.GET.get('sort')
    current_dir = request.GET.get('dir') if request.GET.get('dir') in ('asc', 'desc') else 'asc'

    sort_keys = {key: key_func for key, _label, key_func in column_defs}
    if current_sort in sort_keys:
        items.sort(key=sort_keys[current_sort], reverse=(current_dir == 'desc'))

    columns = []
    for key, label, _key_func in column_defs:
        is_current = key == current_sort
        columns.append({
            'key': key,
            'label': label,
            'next_dir': 'asc' if not is_current or current_dir == 'desc' else 'desc',
            'arrow': ('▲' if current_dir == 'asc' else '▼') if is_current else '',
        })
    return columns


@login_required
def program_list(request):
    programs = list(Program.objects.all())
    for program in programs:
        applications = list(program.applications.all())
        program.total_applications = len(applications)
        program.status_counts = _status_counts(applications)

    columns = _sort_and_build_columns(request, programs, PROGRAM_LIST_COLUMNS)

    return render(request, 'funding/program_list.html', {'programs': programs, 'columns': columns})


@login_required
def program_create(request):
    if request.method == 'POST':
        form = ProgramForm(request.POST)
        if form.is_valid():
            deadline_date = form.cleaned_data['deadline']
            deadline = timezone.make_aware(datetime.datetime.combine(deadline_date, datetime.time(23, 59)))
            program = Program.objects.create(
                name=form.cleaned_data['name'],
                deadline=deadline,
                created_by=request.user,
            )
            messages.success(request, render_text('messages.program_created', name=program.name))
            return redirect('program_list')
    else:
        form = ProgramForm()
    return render(request, 'funding/program_form.html', {'form': form})


@login_required
def program_detail(request, program_id):
    program = get_object_or_404(Program, pk=program_id)
    applications = list(program.applications.all())

    columns = _sort_and_build_columns(request, applications, APPLICATION_LIST_COLUMNS)

    return render(request, 'funding/program_detail.html', {
        'program': program,
        'applications': applications,
        'columns': columns,
    })


@login_required
def application_detail(request, application_id):
    application = get_object_or_404(Application, pk=application_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        form = DecisionForm(request.POST)
        if form.is_valid():
            comment = form.cleaned_data['comment']
            try:
                if action == 'accept':
                    application.accept(request.user, comment)
                    messages.success(request, get_text('messages.application_accepted'))
                elif action == 'refuse':
                    application.refuse(request.user, comment)
                    messages.success(request, get_text('messages.application_refused'))
                elif action == 'approve_work':
                    application.approve_work(request.user, comment)
                    messages.success(request, get_text('messages.work_approved'))
                else:
                    messages.error(request, get_text('messages.unknown_action'))
            except ValueError as exc:
                messages.error(request, str(exc))
        return redirect('application_detail', application_id=application.id)

    return render(request, 'funding/application_detail.html', {
        'application': application,
        'decision_form': DecisionForm(),
        'status_history': application.status_history(),
    })


@login_required
def application_document(request, application_id, field):
    application = get_object_or_404(Application, pk=application_id)
    if field not in APPLICATION_DOCUMENT_FIELDS:
        raise Http404(get_text('errors.unknown_document'))

    filename_field, mimetype_field, blob_field = APPLICATION_DOCUMENT_FIELDS[field]
    blob = getattr(application, blob_field)
    if not blob:
        raise Http404(get_text('errors.document_not_uploaded_yet'))

    response = HttpResponse(bytes(blob), content_type=getattr(application, mimetype_field))
    response['Content-Disposition'] = f'inline; filename="{getattr(application, filename_field)}"'
    return response


def _status_counts(applications):
    counts = {key: 0 for key in Application.STATUS_LABELS}
    for application in applications:
        counts[application.status] += 1
    return counts
