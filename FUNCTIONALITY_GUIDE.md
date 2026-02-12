# ESOP Platform Functionality Guide (Current State)

This guide documents the functionality implemented so far in the ESOP Administration Platform. It covers web UI features, API endpoints, background jobs, integrations, data model highlights, security controls, and how to use each capability.

**Quick Map**

- Web UI routes: `config/urls.py`
- API routes: `apps/api/urls.py`
- Core domain apps: `apps/beneficiaries`, `apps/dividends`, `apps/month_end`, `apps/documents`, `apps/tenants`
- Security and shared utilities: `common/`
- Integrations: `apps/integrations/`
- Audit logging: `apps/audit/`

**Environment And Setup**

1. Create and configure `.env` using `.env.example`.
2. Ensure Postgres and Redis are available.
3. Run migrations and create a superuser.

```bash
python manage.py migrate
python manage.py createsuperuser
```

4. Run the development server.

```bash
python manage.py runserver
```

5. Optional: seed JSE company reference data.

```bash
python manage.py seed_jse_companies
```

**Authentication And Access Control**

- Custom user model with roles: `Scheme Admin` and `Beneficiary`.
- Tenant scoping by `Company` for all tenant-owned data.
- Login flow with optional MFA and account lockout.
- Rate limiting on login.

How to use:

1. Login at `/accounts/login/`.
2. If MFA is enabled and the user has MFA enabled, you are redirected to `/accounts/mfa/verify/`.
3. Logout is POST-only at `/accounts/logout/`.

Notes:

- Account lockout after `MAX_FAILED_LOGIN_ATTEMPTS` with a timed unlock (`ACCOUNT_LOCKOUT_MINUTES`).
- MFA verification is stubbed and accepts any 6-digit token if a secret exists.

**Role-Specific How-To**

Scheme Admin (Internal):

1. Log in at `/accounts/login/`.
2. Create or select a company at `/companies/`.
3. Manage beneficiaries for that company at `/beneficiaries/<company_uuid>/`.
4. Upload and approve documents at `/documents/<company_uuid>/`.
5. Create and run dividend workflows at `/dividends/<company_uuid>/`.
6. Create and run month-end workflows at `/month-end/<company_uuid>/`.
7. Use API tokens to automate actions as needed.

Beneficiary (External):

1. Log in at `/accounts/login/`.
2. Access is restricted to your own data in the API (allocations and vesting events).
3. The beneficiary portal UI is not implemented yet, so access is currently API-only.

**Company (Tenant) Management**

- Create and manage client companies.
- Optional JSE metadata, which can be auto-filled using the JSE search widget.

Web UI:

- List: `/companies/`
- Create: `/companies/create/`
- Detail: `/companies/<company_uuid>/`

How to use:

1. Navigate to `/companies/` to view all companies.
2. Use the search box to filter by name, registration number, or ticker.
3. Click `Create` to add a new company.
4. Use the JSE search box to auto-fill ticker/ISIN/sector. This triggers a background enrichment request.

**Beneficiary Management**

- Tenant-scoped beneficiaries with encrypted PII (ID number, bank account number).
- Validations for SA ID numbers and share totals.
- Full CRUD in UI and API.

Web UI:

- List: `/beneficiaries/<company_uuid>/`
- Create: `/beneficiaries/<company_uuid>/create/`
- Detail: `/beneficiaries/<company_uuid>/<beneficiary_uuid>/`
- Update: `/beneficiaries/<company_uuid>/<beneficiary_uuid>/edit/`

How to use:

1. Open the list view for a company.
2. Use `q` and `status` filters to search.
3. Create or update a beneficiary; share totals must balance.
4. Bank and ID numbers are stored encrypted at rest.

**Document Management**

- Secure file storage per company.
- Quarantine workflow for uploads.
- Controlled download stream (no direct file access).

Web UI:

- List: `/documents/<company_uuid>/`
- Upload: `/documents/<company_uuid>/upload/`
- Detail: `/documents/<company_uuid>/<doc_uuid>/`
- Download: `/documents/<company_uuid>/<doc_uuid>/download/`
- Update status: `/documents/<company_uuid>/<doc_uuid>/status/`

How to use:

1. Upload a document; it starts in `Quarantine`.
2. Update status to `Active` to allow download.
3. Downloads are streamed through an authenticated view with audit logging.

Upload controls:

- MIME and magic byte validation.
- Max size controlled by `MAX_UPLOAD_SIZE_MB`.
- Allowed types: PDF, PNG, JPEG.

**Dividend Distribution**

- Dividend runs with a state machine: `Draft → Approved → Processing → Completed` or `Failed`.
- Allocation generation for active beneficiaries with vested shares.
- Payment submission tasks to a banking integration (stub).

Web UI:

- List: `/dividends/<company_uuid>/`
- Create: `/dividends/<company_uuid>/create/`
- Detail: `/dividends/<company_uuid>/<run_uuid>/`
- Update (draft only): `/dividends/<company_uuid>/<run_uuid>/edit/`
- Approve: `/dividends/<company_uuid>/<run_uuid>/approve/`
- Process: `/dividends/<company_uuid>/<run_uuid>/process/`
- Reset: `/dividends/<company_uuid>/<run_uuid>/reset/`

How to use:

1. Create a dividend run in `Draft`.
2. A different user (four-eyes principle) approves it.
3. Process the run to generate allocations.
4. Review allocations and totals in the detail view.
5. Reset to draft if needed (removes allocations).

Background tasks:

- `dividends.process_run` creates allocations for eligible beneficiaries.
- `dividends.submit_payments` submits EFT payments for pending allocations.

Key calculations:

- `gross = vested_shares × dividend_per_share`
- `tax = gross × dwt_rate`
- `net = gross − tax`

**Month-End Processing**

- Month-end runs with a state machine: `Draft → Approved → Processing → Completed` or `Failed`.
- Creates vesting events that sell all vested shares for active beneficiaries.
- Tax directives and payment submissions in background tasks.

Web UI:

- List: `/month-end/<company_uuid>/`
- Create: `/month-end/<company_uuid>/create/`
- Detail: `/month-end/<company_uuid>/<run_uuid>/`
- Update (draft only): `/month-end/<company_uuid>/<run_uuid>/edit/`
- Approve: `/month-end/<company_uuid>/<run_uuid>/approve/`
- Process: `/month-end/<company_uuid>/<run_uuid>/process/`
- Reset: `/month-end/<company_uuid>/<run_uuid>/reset/`

How to use:

1. Create a month-end run for a period.
2. Approve with a different user.
3. Process the run with a share price and tax rate.
4. Review vesting events and totals.
5. Reset to draft to clear events.

Background tasks:

- `month_end.process_run` creates vesting events.
- `month_end.submit_tax_directives` submits directives to SARS (stub).
- `month_end.submit_payments` submits EFT payments (stub).

**Integrations (Stub Implementations)**

- Banking: EFT and NAEDO payments, payment status checks.
- SARS: Tax directive submission and status polling.
- Velocity Trade: trade execution and contract notes.
- Payroll: employee sync and IRP5 upload.
- JSE: Yahoo Finance enrichment for share price and market cap.

How to use:

1. Integrations are called from services and Celery tasks.
2. Logs are stored in `IntegrationLog` with request/response metadata.
3. JSE enrichment can be triggered from the UI or API.

**Audit Logging**

- Immutable audit logs for authentication, data changes, file actions, and workflows.
- Audit log creation is centralized in `apps/audit/services.py`.

How to use:

- Audit logging happens automatically from services and views.
- Direct updates or deletes are blocked at the model level.

**REST API (Versioned)**

All API routes are under `/api/v1/` and use token or session authentication.

Authentication:

- Token endpoint: `POST /api/v1/auth/token/`

How to use:

1. Obtain a token using username and password.
2. Include the token in the `Authorization: Token <token>` header.

API Endpoints:

- `GET/POST /api/v1/beneficiaries/`
- `GET/PUT/PATCH/DELETE /api/v1/beneficiaries/<id>/`
- `GET/POST /api/v1/dividend-runs/`
- `POST /api/v1/dividend-runs/<id>/approve/`
- `POST /api/v1/dividend-runs/<id>/process/`
- `POST /api/v1/dividend-runs/<id>/reset/`
- `GET /api/v1/dividend-allocations/?run=<run_id>`
- `GET/POST /api/v1/month-end-runs/`
- `POST /api/v1/month-end-runs/<id>/approve/`
- `POST /api/v1/month-end-runs/<id>/process/`
- `POST /api/v1/month-end-runs/<id>/reset/`
- `GET /api/v1/vesting-events/?run=<run_id>`
- `GET /api/v1/tax-directives/?run=<run_id>`
- `GET /api/v1/jse-companies/?q=<query>`
- `POST /api/v1/jse-companies/<id>/enrich/`

API Notes:

- Most endpoints require `Scheme Admin` privileges.
- Beneficiaries can only access their own allocations/events.
- API errors are normalized through a custom exception handler.

API Examples:

Obtain token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

Example token response:

```json
{"token":"<token-value>"}
```

List beneficiaries (scheme admin):

```bash
curl http://localhost:8000/api/v1/beneficiaries/ \
  -H "Authorization: Token <token-value>"
```

Create a beneficiary (scheme admin):

```bash
curl -X POST http://localhost:8000/api/v1/beneficiaries/ \
  -H "Authorization: Token <token-value>" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_number": "EMP-1001",
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "total_shares": 1000,
    "vested_shares": 250,
    "unvested_shares": 750
  }'
```

Approve a dividend run:

```bash
curl -X POST http://localhost:8000/api/v1/dividend-runs/<run_id>/approve/ \
  -H "Authorization: Token <token-value>"
```

Process a month-end run:

```bash
curl -X POST http://localhost:8000/api/v1/month-end-runs/<run_id>/process/ \
  -H "Authorization: Token <token-value>" \
  -H "Content-Type: application/json" \
  -d '{"share_price":"150.25","tax_rate":"0.3500"}'
```

**Security Features**

- Role-based access control for web and API.
- Tenant scoping for all company-owned data.
- Account lockout and login rate limiting.
- CSRF protection for web forms.
- Secure document upload with MIME and magic byte checks.
- Field-level encryption for ID numbers and bank accounts.
- Admin IP allowlist support for `/admin/`.

**Health Check**

- Unauthenticated endpoint: `GET /health/` returns `{ "status": "ok" }`.

**Known Gaps And Stubs (Current State)**

- MFA verification is stubbed (accepts any 6-digit token when a secret exists).
- Banking, SARS, Payroll, Velocity Trade integrations are stubs.
- Dividend and month-end payment submission tasks depend on stub integrations.
- Some API serializers use field names that do not match model fields for vesting events and tax directives.
- No end-user beneficiary portal views are implemented yet.
- No UI screens for audit logs or integration logs.

**Roadmap / Missing Features Checklist**

1. Replace MFA stub with real TOTP verification.
2. Implement beneficiary portal UI (allocations, vesting events, documents).
3. Add admin UI for audit logs and integration logs.
4. Build real integrations for Banking, SARS, Payroll, and Velocity Trade.
5. Implement robust file malware scanning for document uploads.
6. Fix API serializer field mismatches for vesting events and tax directives.
7. Add export/download reports for dividend and month-end runs.
8. Add background job monitoring and retry dashboards.
9. Add multi-factor admin actions for financial approvals.
10. Add automated reconciliation and payment file generation.

**Where To Look In Code**

- Core URLs: `config/urls.py`
- Security mixins: `common/permissions.py`
- Upload validators: `common/validators.py`
- Encryption: `common/encryption.py`
- Dividend logic: `apps/dividends/services.py`
- Month-end logic: `apps/month_end/services.py`
- Integration clients: `apps/integrations/*.py`
- API behavior: `apps/api/views.py`

