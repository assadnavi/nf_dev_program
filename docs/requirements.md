# Functional Requirements — Funding Program Automation

## 1. Purpose

Automate the administrative lifecycle of a funding program: opening a call for applications, collecting applications from external organizations, reviewing and deciding on each one, collecting an upfront invoice to trigger a 50% advance payment, and — once Admin confirms the funded work is done — collecting a final invoice for the remaining 50%.

This is a standalone application, independent from any other existing system.

## 2. Actors

- **Admin** — internal team, the only actor allowed to create and manage funding programs and review applications. Composed of multiple individual members, each with their own account.
- **Applicant** — an external organization submitting an application. Does not have an account and never authenticates.

## 3. Functional Requirements

### 3.1 Program Management

- Only Admin can create a program.
- A program has: a name and a submission deadline.
- Multiple programs can exist and run in parallel, each independent of the others.
- A program opens for submissions immediately upon creation (no draft/pre-publish state).
- The deadline only gates new submissions — after the deadline passes, Admin can still review and decide on already-submitted applications at any time.
- All programs share the same application form template (see 3.2).

### 3.2 Application Submission

- Applicants access a public submission page specific to a program (no login required).
- The form is fixed and identical across all programs, with two mandatory fields:
  - **email** (text)
  - **attachment** — the project proposal document (`.doc` or `.pdf`, no further content constraints)
- Submission is one-shot: once submitted, the applicant cannot edit or resubmit.
- There is no automatic validation of the applicant's email against any list. Admin is expected to know which organizations are legitimate and manually verify this during review.
- No confirmation email or notification is sent to the applicant upon submission.

### 3.3 Application Review

- Admin reviews submitted applications individually (list + detail view of form data and attached document).
- For each application, Admin decides: **Accept** or **Refuse**.
- Admin can optionally fill in a comment/reason alongside the decision. It is never required.
- There is no consensus/voting mechanism — any Admin member's decision is final.
- Refusing an application is a terminal action — no further steps follow.
- No automatic notification is sent to the applicant on acceptance or refusal. Admin is responsible for informing applicants by email, entirely outside the system.
- Past applications remain visible to Admin regardless of their outcome — accepted, refused, or completed applications are never hidden or archived out of view.
- When Admin opens an application, they can see its status history: when it was submitted, when and how it was decided, when each invoice was received, and when the work was approved.

### 3.4 Post-Acceptance: Upfront Invoice, Work Approval, Final Invoice

- Each application has a unique, unguessable access link that lets the applicant reopen that specific application at any time. The same link is reused for everything below — no new link is issued at any stage.
- This link is not shown to the applicant automatically — it is visible to Admin on the application's detail page, so Admin can share it manually (e.g. paste it into their own acceptance email).
- Once an application is accepted, the applicant uses their link to submit an **upfront invoice** (PDF). Receiving this authorizes Admin to pay 50% of the funding upfront (the actual payment happens outside the system).
- After the upfront invoice is received, Admin must **approve the work** once the funded project is actually completed, before the applicant can proceed. This is a manual Admin decision, distinct from the initial Accept/Refuse decision.
- Once Admin approves the work, the applicant uses the same link to submit a **final invoice** (PDF), covering the remaining 50%.
- No additional email/identity check is performed at either invoice step — possession of the link is sufficient.
- There is no deadline for either invoice or for Admin's work approval.
- Once the final invoice is uploaded, the application is automatically marked as complete. This is the actual end of the process — no further review or action follows.

### 3.5 Communication

- The system does not send any automated emails or notifications at any point in the process (submission receipt, acceptance, refusal, invoice requests, or work approval).
- All communication with applicants is handled manually by Admin, outside of the system, using information Admin can see in the admin views (including the unique application link).

## 4. Application Lifecycle (states)

```
Submitted → Accepted (Upfront Invoice Pending)
          → Upfront Invoice Received (Awaiting Work Approval)
          → Work Approved (Final Invoice Pending)
          → Complete
          → Refused (terminal, reachable only from Submitted)
```

- **Submitted**: application received, awaiting Admin's decision.
- **Accepted (Upfront Invoice Pending)**: Admin approved the application; upfront invoice not yet received.
- **Upfront Invoice Received (Awaiting Work Approval)**: upfront invoice received; Admin has not yet confirmed the funded work is done.
- **Work Approved (Final Invoice Pending)**: Admin confirmed the work is done; final invoice not yet received.
- **Refused**: Admin rejected the application. Terminal — no further action.
- **Complete**: final invoice received. Terminal — the actual end of the process.

## 5. Out of Scope

- Applicant accounts, login, or SSO.
- Editing or resubmitting an application after initial submission.
- Any automatic email/notification sending.
- A deadline or reminder mechanism for either invoice or for work approval.
- Any process or workflow after the final invoice is submitted (e.g. actually disbursing funds, accounting, reporting).
- Tracking whether Admin has actually paid out either invoice (see requirements likely to be added in the future — design should keep this an easy addition, not build it now).
- Automatic filtering/validation of applicant emails against a known-organization list.
- Multiple/configurable form templates — the form is fixed and shared by all programs.

## 6. Assumptions & Scale

- Expected volume: ~4 programs per year, ~50 applicants per program (~200 applications/year).
- Admin members authenticate via username/password for now; the system should be designed so a company SSO provider could be integrated later without reshaping this model.
- No integration with any external system is required.
- No stated compliance or data-retention requirements.
