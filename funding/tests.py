import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Application, Program


def pdf_file(name='proposal.pdf', content=b'%PDF-1.4 test content'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


class ApplicationTransitionTests(TestCase):
    """Model-level tests of the state machine in models.py (design.md §3)."""

    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw')
        self.program = Program.objects.create(
            name='Grant', deadline=timezone.now() + datetime.timedelta(days=30),
            created_by=self.admin,
        )
        self.application = Application.objects.create(
            program=self.program, email='org@example.com',
            proposal_filename='p.pdf', proposal_mimetype='application/pdf', proposal_blob=b'data',
        )

    def test_full_lifecycle(self):
        app = self.application
        self.assertEqual(app.status, 'submitted')
        self.assertEqual(app.status_label, 'Submitted')

        app.accept(self.admin, comment='looks good')
        self.assertEqual(app.status, 'upfront_invoice_pending')

        app.receive_upfront_invoice('upfront.pdf', 'application/pdf', b'upfront-bytes')
        self.assertEqual(app.status, 'awaiting_work_approval')

        app.approve_work(self.admin, comment='work confirmed')
        self.assertEqual(app.status, 'final_invoice_pending')

        app.receive_final_invoice('final.pdf', 'application/pdf', b'final-bytes')
        self.assertEqual(app.status, 'complete')

        history = app.status_history()
        labels = [entry[0] for entry in history]
        self.assertEqual(labels, [
            'Submitted', 'Accepted', 'Upfront invoice received',
            'Work approved', 'Final invoice received (Complete)',
        ])

    def test_refuse_is_terminal(self):
        app = self.application
        app.refuse(self.admin, comment='not eligible')
        self.assertEqual(app.status, 'refused')
        with self.assertRaises(ValueError):
            app.accept(self.admin)

    def test_cannot_skip_ahead(self):
        app = self.application
        with self.assertRaises(ValueError):
            app.receive_upfront_invoice('x.pdf', 'application/pdf', b'x')
        app.accept(self.admin)
        with self.assertRaises(ValueError):
            app.approve_work(self.admin)
        with self.assertRaises(ValueError):
            app.receive_final_invoice('x.pdf', 'application/pdf', b'x')
        app.receive_upfront_invoice('u.pdf', 'application/pdf', b'u')
        with self.assertRaises(ValueError):
            app.receive_final_invoice('x.pdf', 'application/pdf', b'x')

    def test_cannot_double_decide(self):
        app = self.application
        app.accept(self.admin)
        with self.assertRaises(ValueError):
            app.accept(self.admin)
        with self.assertRaises(ValueError):
            app.refuse(self.admin)

    def test_access_token_is_stable_across_lifecycle(self):
        app = self.application
        token = app.access_token
        app.accept(self.admin)
        app.receive_upfront_invoice('u.pdf', 'application/pdf', b'u')
        app.approve_work(self.admin)
        app.receive_final_invoice('f.pdf', 'application/pdf', b'f')
        app.refresh_from_db()
        self.assertEqual(app.access_token, token)


class PublicApplicationFlowTests(TestCase):
    """End-to-end via the Django test client: public submission through to Complete."""

    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw')
        self.program = Program.objects.create(
            name='Grant', deadline=timezone.now() + datetime.timedelta(days=30),
            created_by=self.admin,
        )

    def test_full_flow_through_browser_like_client(self):
        # Applicant submits.
        response = self.client.post(reverse('apply', args=[self.program.id]), {
            'email': 'org@example.com',
            'proposal': pdf_file(),
        })
        self.assertEqual(response.status_code, 200)
        application = Application.objects.get(program=self.program)
        self.assertEqual(application.status, 'submitted')

        # Admin logs in and accepts.
        self.client.login(username='admin', password='pw')
        response = self.client.post(
            reverse('application_detail', args=[application.id]),
            {'action': 'accept', 'comment': 'great fit'},
        )
        self.assertRedirects(response, reverse('application_detail', args=[application.id]))
        application.refresh_from_db()
        self.assertEqual(application.status, 'upfront_invoice_pending')
        self.client.logout()

        # Applicant uploads the upfront invoice via their token link (no login).
        status_url = reverse('application_status', args=[application.access_token])
        response = self.client.post(status_url, {'invoice': pdf_file('upfront.pdf')})
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, 'awaiting_work_approval')

        # Admin approves the work.
        self.client.login(username='admin', password='pw')
        response = self.client.post(
            reverse('application_detail', args=[application.id]),
            {'action': 'approve_work', 'comment': ''},
        )
        application.refresh_from_db()
        self.assertEqual(application.status, 'final_invoice_pending')
        self.client.logout()

        # Applicant uploads the final invoice.
        response = self.client.post(status_url, {'invoice': pdf_file('final.pdf')})
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, 'complete')

        # Re-visiting the same link now just shows completion, no form.
        response = self.client.get(status_url)
        self.assertContains(response, 'now complete')
        self.assertNotContains(response, '<form')

    def test_refuse_flow(self):
        self.client.post(reverse('apply', args=[self.program.id]), {
            'email': 'org@example.com',
            'proposal': pdf_file(),
        })
        application = Application.objects.get(program=self.program)
        self.client.login(username='admin', password='pw')
        self.client.post(
            reverse('application_detail', args=[application.id]),
            {'action': 'refuse', 'comment': ''},
        )
        application.refresh_from_db()
        self.assertEqual(application.status, 'refused')
        self.client.logout()

        response = self.client.get(reverse('application_status', args=[application.access_token]))
        self.assertContains(response, 'not accepted')
        self.assertNotContains(response, '<form')

    def test_closed_program_rejects_submission(self):
        closed_program = Program.objects.create(
            name='Closed grant',
            deadline=timezone.now() - datetime.timedelta(days=1),
            created_by=self.admin,
        )
        response = self.client.get(reverse('apply', args=[closed_program.id]))
        self.assertContains(response, 'closed')

        response = self.client.post(reverse('apply', args=[closed_program.id]), {
            'email': 'org@example.com',
            'proposal': pdf_file(),
        })
        self.assertFalse(Application.objects.filter(program=closed_program).exists())

    def test_rejects_non_pdf_or_word_proposal(self):
        response = self.client.post(reverse('apply', args=[self.program.id]), {
            'email': 'org@example.com',
            'proposal': SimpleUploadedFile('proposal.txt', b'not a pdf', content_type='text/plain'),
        })
        self.assertEqual(response.status_code, 200)  # re-renders form with errors
        self.assertFalse(Application.objects.filter(program=self.program).exists())

    def test_rejects_non_pdf_invoice(self):
        application = Application.objects.create(
            program=self.program, email='org@example.com',
            proposal_filename='p.pdf', proposal_mimetype='application/pdf', proposal_blob=b'data',
        )
        application.accept(self.admin)
        status_url = reverse('application_status', args=[application.access_token])
        response = self.client.post(status_url, {
            'invoice': SimpleUploadedFile('invoice.docx', b'not a pdf', content_type='application/msword'),
        })
        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertIsNone(application.upfront_invoice_received_at)


class ProgramCreationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw')
        self.client.login(username='admin', password='pw')

    def test_deadline_date_becomes_end_of_day(self):
        response = self.client.post(reverse('program_create'), {
            'name': 'Grant',
            'deadline': '2026-01-03',
        })
        program = Program.objects.get(name='Grant')
        self.assertRedirects(response, reverse('program_list'))
        local_deadline = timezone.localtime(program.deadline)
        self.assertEqual(
            (local_deadline.year, local_deadline.month, local_deadline.day, local_deadline.hour, local_deadline.minute),
            (2026, 1, 3, 23, 59),
        )


class RootRedirectTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw')

    def test_anonymous_visitor_redirected_to_login(self):
        response = self.client.get(reverse('root'))
        self.assertRedirects(response, reverse('login'))

    def test_logged_in_admin_redirected_to_dashboard(self):
        self.client.login(username='admin', password='pw')
        response = self.client.get(reverse('root'))
        self.assertRedirects(response, reverse('program_list'))


class ProgramListSortingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw')
        self.client.login(username='admin', password='pw')
        Program.objects.create(name='Beta', deadline=timezone.now() + datetime.timedelta(days=10), created_by=self.admin)
        Program.objects.create(name='Alpha', deadline=timezone.now() + datetime.timedelta(days=30), created_by=self.admin)
        Program.objects.create(name='Charlie', deadline=timezone.now() + datetime.timedelta(days=20), created_by=self.admin)

    def test_sort_by_name_ascending_and_descending(self):
        response = self.client.get(reverse('program_list'), {'sort': 'name', 'dir': 'asc'})
        self.assertEqual([p.name for p in response.context['programs']], ['Alpha', 'Beta', 'Charlie'])

        response = self.client.get(reverse('program_list'), {'sort': 'name', 'dir': 'desc'})
        self.assertEqual([p.name for p in response.context['programs']], ['Charlie', 'Beta', 'Alpha'])

    def test_sort_by_deadline(self):
        response = self.client.get(reverse('program_list'), {'sort': 'deadline', 'dir': 'asc'})
        self.assertEqual([p.name for p in response.context['programs']], ['Beta', 'Charlie', 'Alpha'])

    def test_unsorted_column_link_defaults_to_ascending_next(self):
        response = self.client.get(reverse('program_list'))
        columns = {c['key']: c for c in response.context['columns']}
        self.assertEqual(columns['name']['next_dir'], 'asc')
        self.assertEqual(columns['name']['arrow'], '')


class ApplicationListSortingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw')
        self.client.login(username='admin', password='pw')
        self.program = Program.objects.create(
            name='Grant', deadline=timezone.now() + datetime.timedelta(days=30), created_by=self.admin,
        )
        Application.objects.create(
            program=self.program, email='beta@example.com',
            proposal_filename='p.pdf', proposal_mimetype='application/pdf', proposal_blob=b'data',
        )
        Application.objects.create(
            program=self.program, email='alpha@example.com',
            proposal_filename='p.pdf', proposal_mimetype='application/pdf', proposal_blob=b'data',
        )

    def test_sort_by_email_ascending_and_descending(self):
        response = self.client.get(reverse('program_detail', args=[self.program.id]), {'sort': 'email', 'dir': 'asc'})
        self.assertEqual(
            [a.email for a in response.context['applications']],
            ['alpha@example.com', 'beta@example.com'],
        )

        response = self.client.get(reverse('program_detail', args=[self.program.id]), {'sort': 'email', 'dir': 'desc'})
        self.assertEqual(
            [a.email for a in response.context['applications']],
            ['beta@example.com', 'alpha@example.com'],
        )


class AccessControlTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw')
        self.program = Program.objects.create(
            name='Grant', deadline=timezone.now() + datetime.timedelta(days=30),
            created_by=self.admin,
        )
        self.application = Application.objects.create(
            program=self.program, email='org@example.com',
            proposal_filename='p.pdf', proposal_mimetype='application/pdf', proposal_blob=b'data',
        )

    def test_dashboard_requires_login(self):
        for url in [
            reverse('program_list'),
            reverse('program_create'),
            reverse('program_detail', args=[self.program.id]),
            reverse('application_detail', args=[self.application.id]),
            reverse('application_document', args=[self.application.id, 'proposal']),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('login'), response.url)

    def test_public_pages_do_not_require_login(self):
        response = self.client.get(reverse('apply', args=[self.program.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('application_status', args=[self.application.access_token]))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_download_proposal_once_logged_in(self):
        self.client.login(username='admin', password='pw')
        response = self.client.get(reverse('application_document', args=[self.application.id, 'proposal']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'data')
        self.assertEqual(response['Content-Type'], 'application/pdf')
