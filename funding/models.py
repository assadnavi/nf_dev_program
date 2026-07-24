import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .site_text import get_text


def generate_access_token():
    return secrets.token_urlsafe(32)


class Program(models.Model):
    name = models.CharField(max_length=255)
    deadline = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def is_open_for_submissions(self):
        return timezone.now() < self.deadline


class Application(models.Model):
    SUBMITTED = 'submitted'
    ACCEPTED = 'accepted'
    REFUSED = 'refused'
    STATE_CHOICES = [
        (SUBMITTED, 'Submitted'),
        (ACCEPTED, 'Accepted'),
        (REFUSED, 'Refused'),
    ]

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='applications')
    access_token = models.CharField(max_length=64, unique=True, default=generate_access_token, editable=False)
    email = models.EmailField()

    proposal_filename = models.CharField(max_length=255)
    proposal_mimetype = models.CharField(max_length=255)
    proposal_blob = models.BinaryField()

    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=SUBMITTED)
    decision_comment = models.TextField(blank=True, null=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='decided_applications',
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    upfront_invoice_filename = models.CharField(max_length=255, blank=True, null=True)
    upfront_invoice_mimetype = models.CharField(max_length=255, blank=True, null=True)
    upfront_invoice_blob = models.BinaryField(blank=True, null=True)
    upfront_invoice_received_at = models.DateTimeField(null=True, blank=True)

    work_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='work_approved_applications',
    )
    work_approved_at = models.DateTimeField(null=True, blank=True)
    work_approval_comment = models.TextField(blank=True, null=True)

    final_invoice_filename = models.CharField(max_length=255, blank=True, null=True)
    final_invoice_mimetype = models.CharField(max_length=255, blank=True, null=True)
    final_invoice_blob = models.BinaryField(blank=True, null=True)
    final_invoice_received_at = models.DateTimeField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.email} / {self.program.name}'

    # --- derived status (see design.md §3) ---

    @property
    def status(self):
        if self.state == self.REFUSED:
            return 'refused'
        if self.state == self.SUBMITTED:
            return 'submitted'
        # state == accepted
        if not self.upfront_invoice_received_at:
            return 'upfront_invoice_pending'
        if not self.work_approved_at:
            return 'awaiting_work_approval'
        if not self.final_invoice_received_at:
            return 'final_invoice_pending'
        return 'complete'

    STATUS_LABELS = get_text('application_status_labels')

    @property
    def status_label(self):
        return self.STATUS_LABELS[self.status]

    # --- centralized state transitions (see design.md §8: single insertion point per transition) ---

    def accept(self, admin_user, comment=''):
        if self.state != self.SUBMITTED:
            raise ValueError(get_text('errors.only_submitted_can_be_accepted'))
        self.state = self.ACCEPTED
        self.decided_by = admin_user
        self.decided_at = timezone.now()
        self.decision_comment = comment
        self.save()

    def refuse(self, admin_user, comment=''):
        if self.state != self.SUBMITTED:
            raise ValueError(get_text('errors.only_submitted_can_be_refused'))
        self.state = self.REFUSED
        self.decided_by = admin_user
        self.decided_at = timezone.now()
        self.decision_comment = comment
        self.save()

    def receive_upfront_invoice(self, filename, mimetype, blob):
        if self.status != 'upfront_invoice_pending':
            raise ValueError(get_text('errors.upfront_invoice_not_expected'))
        self.upfront_invoice_filename = filename
        self.upfront_invoice_mimetype = mimetype
        self.upfront_invoice_blob = blob
        self.upfront_invoice_received_at = timezone.now()
        self.save()

    def approve_work(self, admin_user, comment=''):
        if self.status != 'awaiting_work_approval':
            raise ValueError(get_text('errors.work_approval_not_expected'))
        self.work_approved_by = admin_user
        self.work_approved_at = timezone.now()
        self.work_approval_comment = comment
        self.save()

    def receive_final_invoice(self, filename, mimetype, blob):
        if self.status != 'final_invoice_pending':
            raise ValueError(get_text('errors.final_invoice_not_expected'))
        self.final_invoice_filename = filename
        self.final_invoice_mimetype = mimetype
        self.final_invoice_blob = blob
        self.final_invoice_received_at = timezone.now()
        self.save()

    # --- status history (see design.md §5) ---

    def status_history(self):
        labels = get_text('status_history_labels')
        history = [(labels['submitted'], self.submitted_at, None)]
        if self.decided_at:
            label = labels['accepted'] if self.state == self.ACCEPTED else labels['refused']
            history.append((label, self.decided_at, self.decision_comment))
        if self.upfront_invoice_received_at:
            history.append((labels['upfront_invoice_received'], self.upfront_invoice_received_at, None))
        if self.work_approved_at:
            history.append((labels['work_approved'], self.work_approved_at, self.work_approval_comment))
        if self.final_invoice_received_at:
            history.append((labels['final_invoice_received'], self.final_invoice_received_at, None))
        return history
