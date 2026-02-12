# ESOP Platform Architecture

**Document Version**: 1.0
**Last Updated**: 2026-02-11
**Audience**: Developers and architects learning this codebase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Core Architectural Patterns](#core-architectural-patterns)
4. [Data Model Architecture](#data-model-architecture)
5. [Security Architecture](#security-architecture)
6. [Application Layer](#application-layer)
7. [Integration Architecture](#integration-architecture)
8. [Data Flow Patterns](#data-flow-patterns)
9. [Scalability and Performance](#scalability-and-performance)

---

## Executive Summary

This is a **multi-tenant Django application** for managing Employee Share Ownership Plans (ESOP) in South Africa. The platform handles:

- **Beneficiary management** (employees in share schemes)
- **Dividend distributions** (calculating and paying dividends to beneficiaries)
- **Month-end processing** (vesting events, share sales, tax directives)
- **Document management** (secure storage of scheme documents)
- **Integration with external systems** (SARS, JSE, banking, payroll)

The architecture prioritizes:

1. **Security**: Multi-tenant data isolation, encrypted PII, audit logging
2. **Compliance**: Immutable audit trails, four-eyes approval, tax calculations
3. **Maintainability**: Service layer pattern, state machines, clear separation of concerns
4. **Scalability**: Designed for hundreds of companies with thousands of beneficiaries each

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
├────────────────────────────┬────────────────────────────────────┤
│  Web Interface (HTML)      │    API Interface (JSON)            │
│  - Django Templates        │    - Django REST Framework         │
│  - HTMX for interactions   │    - Token + Session Auth          │
│  - Server-rendered pages   │    - Versioned endpoints           │
└────────────────────────────┴────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Class-Based     │  ViewSets        │  Service Layer           │
│  Views (CBVs)    │  (DRF)           │  (Business Logic)        │
│  - List          │  - CRUD          │  - State machines        │
│  - Detail        │  - Custom        │  - Validation            │
│  - Create/Update │    actions       │  - Idempotency           │
│  - State changes │  - Permissions   │  - Audit logging         │
└──────────────────┴──────────────────┴──────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                              │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Django ORM      │  Postgres DB     │  Encrypted Storage       │
│  - Models        │  - JSONB support │  - Fernet encryption     │
│  - Managers      │  - UUID PKs      │  - ID numbers            │
│  - QuerySets     │  - Indexes       │  - Bank accounts         │
└──────────────────┴──────────────────┴──────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INTEGRATION LAYER                            │
├──────────────────┬──────────────────┬──────────────────────────┤
│  External APIs   │  Celery Tasks    │  Integration Logging     │
│  - SARS          │  - Background    │  - Request/response      │
│  - JSE/Yahoo     │  - Retry logic   │  - Error tracking        │
│  - Banking       │  - Scheduling    │  - Idempotency keys      │
└──────────────────┴──────────────────┴──────────────────────────┘
```

### Technology Stack

- **Framework**: Django 4.x
- **API**: Django REST Framework (DRF)
- **Database**: PostgreSQL (with JSONB support)
- **Task Queue**: Celery (implied by integration logs)
- **Encryption**: Fernet (symmetric encryption for PII)
- **Authentication**: Django session + DRF Token
- **Frontend**: Server-rendered templates + HTMX

---

## Core Architectural Patterns

### 1. Multi-Tenancy Pattern

**Concept**: Each client company is a separate "tenant". Their data is logically isolated from other tenants.

**Implementation**:
- Every tenant-scoped model has a `company` foreign key (enforced at DB level)
- All queries MUST filter by `company` to prevent cross-tenant data leakage
- Two isolation mechanisms:
  - **Web**: URLs contain `company_pk`, views load company from URL
  - **API**: User object has `company` field, queries filter by `request.user.company`

**Key Classes**:

```python
# All tenant-scoped models inherit from this
class TenantScopedModel(BaseModel):
    company = models.ForeignKey("tenants.Company", ...)
    objects = TenantScopedManager()  # Provides .for_tenant(company)
```

**Relationships**:
```
Company (Tenant)
  ├── Users (many)
  ├── Beneficiaries (many)
  ├── DividendRuns (many)
  ├── MonthEndRuns (many)
  ├── Documents (many)
  └── IntegrationLogs (many)
```

**Security Notes**:
- Schema is NOT multi-tenant (no separate databases per tenant)
- Row-level security enforced in application code
- Reference data (e.g., JSECompany) is NOT tenant-scoped (shared across all tenants)

---

### 2. Service Layer Pattern

**Concept**: Business logic lives in service functions, not in views or models.

**Why**:
- State transitions require validation (state machines)
- Four-eyes approval requires business rules
- Operations need to be atomic (transactions)
- All state changes must be audited

**Implementation**:

```python
# Service layer example
# apps/dividends/services.py

def approve_run(run: DividendRun, user: User) -> DividendRun:
    # Business rule: four-eyes principle
    if run.created_by == user:
        raise PermissionDenied("You cannot approve a run you created.")

    # State machine validation
    _validate_transition(run, RunStatus.APPROVED)

    # Update and audit
    run.approved_by = user
    run.approved_at = timezone.now()
    _change_status(run, RunStatus.APPROVED)  # Saves and logs
    return run


@transaction.atomic()
def process_run(run: DividendRun) -> DividendRun:
    _validate_transition(run, RunStatus.PROCESSING)
    _change_status(run, RunStatus.PROCESSING)

    try:
        # Idempotent creation
        _create_allocations(run)
        # ... compute totals, update run
        _change_status(run, RunStatus.COMPLETED)
    except Exception as e:
        run.failure_reason = str(e)
        _change_status(run, RunStatus.FAILED)
        raise
```

**Service functions are called by**:
- Web views (CBVs for HTML interface)
- API ViewSet actions (DRF endpoints)
- Celery tasks (background jobs)

**Relationships**:
```
Views/ViewSets
    ↓ calls
Service Layer
    ↓ uses
Models (ORM)
    ↓ writes to
Database
    ↓ creates
Audit Logs
```

---

### 3. State Machine Pattern

**Concept**: Workflows (dividend runs, month-end runs) have defined states and allowed transitions.

**Implementation**:

```python
class RunStatus(models.TextChoices):
    DRAFT = "draft"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

VALID_TRANSITIONS = {
    RunStatus.DRAFT: [RunStatus.APPROVED],
    RunStatus.APPROVED: [RunStatus.PROCESSING, RunStatus.DRAFT],
    RunStatus.PROCESSING: [RunStatus.COMPLETED, RunStatus.FAILED],
    RunStatus.COMPLETED: [],  # Terminal state
    RunStatus.FAILED: [RunStatus.DRAFT],  # Can reset
}
```

**State Transition Flow**:

```
DRAFT
  ↓ approve_run() (requires different user)
APPROVED
  ↓ process_run() (atomic transaction)
PROCESSING
  ↓ (success)       ↓ (failure)
COMPLETED         FAILED
                    ↓ reset_to_draft()
                  DRAFT
```

**Validation**:
```python
def _validate_transition(obj, target_status):
    allowed = VALID_TRANSITIONS.get(obj.status, [])
    if target_status not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition from {obj.status} to {target_status}"
        )
```

**Used in**:
- DividendRun (dividend distributions)
- MonthEndRun (month-end processing)

---

### 4. Audit Logging Pattern

**Concept**: All sensitive actions are logged immutably for compliance and forensics.

**Implementation**:

```python
class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, ...)
    action = models.CharField(choices=AuditAction.choices)
    company = models.ForeignKey(Company, ...)
    details = models.JSONField(default=dict)

    def save(self, *args, **kwargs):
        # Only allow creation, not updates
        if not self._state.adding:
            raise ValueError("AuditLog entries are immutable")
```

**Actions logged**:
- Authentication events (login, logout, password changes)
- Beneficiary CRUD operations
- State transitions (approve, process, reset)
- File operations (upload, download)
- Integration calls to external systems

**Relationships**:
```
User performs Action
    ↓ triggers
Service Layer
    ↓ calls
log_audit()
    ↓ creates
AuditLog (immutable)
    ↓ references
Company + target object
```

---

## Data Model Architecture

### Entity Relationship Diagram

```
┌─────────────┐
│   Company   │ (Tenant boundary)
└──────┬──────┘
       │
       ├──────────────────────────────────────────────────┐
       │                                                   │
       ▼                                                   ▼
┌─────────────┐                                    ┌─────────────┐
│    User     │                                    │ Beneficiary │
│ (Auth)      │                                    │ (Employee)  │
├─────────────┤                                    ├─────────────┤
│ role        │──── one-to-one (optional) ────────│ user        │
│ company (FK)│                                    │ company (FK)│
└─────────────┘                                    │ shares      │
                                                   │ bank details│
                                                   └──────┬──────┘
                                                          │
       ┌──────────────────────────────────────────────────┼───────────────┐
       │                                                   │               │
       ▼                                                   ▼               ▼
┌─────────────┐                                    ┌─────────────┐ ┌─────────────┐
│ DividendRun │                                    │MonthEndRun  │ │  Document   │
├─────────────┤                                    ├─────────────┤ ├─────────────┤
│ status      │                                    │ status      │ │ file        │
│ total_amount│                                    │ period      │ │ category    │
│ created_by  │                                    │ created_by  │ │ beneficiary │
│ approved_by │                                    │ approved_by │ │ (FK)        │
└──────┬──────┘                                    └──────┬──────┘ └─────────────┘
       │                                                   │
       ├─── creates many ──────┐                          ├─── creates many ──────┐
       │                       │                          │                       │
       ▼                       ▼                          ▼                       ▼
┌─────────────┐        ┌─────────────┐          ┌─────────────┐        ┌─────────────┐
│  Dividend   │        │ Integration │          │  Vesting    │        │    Tax      │
│ Allocation  │        │    Log      │          │   Event     │        │  Directive  │
├─────────────┤        ├─────────────┤          ├─────────────┤        ├─────────────┤
│ beneficiary │        │ system      │          │ beneficiary │        │ beneficiary │
│ shares      │        │ operation   │          │ shares      │        │ directive_# │
│ gross/net   │        │ status      │          │ event_type  │        │ status      │
└─────────────┘        └─────────────┘          └─────────────┘        └─────────────┘
```

### Core Models Explained

#### 1. Company (Tenant)
- **Purpose**: Represents a client company using the ESOP platform
- **Key Fields**: name, registration_number, tax_number, jse_ticker (optional)
- **Relationships**: One-to-many with all tenant-scoped models
- **Inheritance**: Inherits from `BaseModel` (has UUID pk, timestamps)

#### 2. User (Authentication)
- **Purpose**: User accounts for scheme admins and beneficiaries
- **Key Fields**: role (SCHEME_ADMIN or BENEFICIARY), company (nullable)
- **Roles**:
  - **SCHEME_ADMIN**: Internal staff, can access multiple companies
  - **BENEFICIARY**: External portal users, scoped to one company
- **Security**: Password validators, account lockout, MFA support
- **Inheritance**: Extends Django's `AbstractUser`

#### 3. Beneficiary (Employee)
- **Purpose**: Employee enrolled in the ESOP scheme
- **Key Fields**:
  - Personal: first_name, last_name, id_number (encrypted), email, phone
  - Shares: total_shares, vested_shares, unvested_shares
  - Bank: account_number (encrypted), bank_name, branch_code
  - Status: ACTIVE, INACTIVE, SUSPENDED, TERMINATED
- **Relationships**:
  - Belongs to one Company (tenant)
  - Optionally linked to one User (for portal access)
  - Has many DividendAllocations, VestingEvents, Documents
- **Encryption**: ID number and bank account number are encrypted at rest using Fernet
- **Inheritance**: Inherits from `TenantScopedModel`

#### 4. DividendRun (Dividend Distribution)
- **Purpose**: A single dividend payment run for a company
- **Key Fields**:
  - Financial: total_amount, dividend_per_share, dwt_rate (tax rate)
  - Dates: record_date, payment_date, declaration_date
  - Status: DRAFT → APPROVED → PROCESSING → COMPLETED/FAILED
  - Tracking: created_by, approved_by, approved_at
- **State Machine**: Uses VALID_TRANSITIONS to enforce workflow
- **Idempotency**: Has unique idempotency_key to prevent duplicates
- **Relationships**:
  - Belongs to one Company
  - Has many DividendAllocations (one per beneficiary)
- **Inheritance**: Inherits from `TenantScopedModel`

#### 5. DividendAllocation (Per-Beneficiary Payment)
- **Purpose**: Individual beneficiary's dividend payment within a run
- **Key Fields**:
  - shares_at_record_date (snapshot)
  - gross_amount, tax_amount, net_amount (calculated)
  - status: PENDING, PAID, FAILED
- **Calculation**:
  - gross = shares × dividend_per_share
  - tax = gross × dwt_rate
  - net = gross - tax
- **Uniqueness**: One allocation per beneficiary per run (DB constraint)
- **Inheritance**: Inherits from `TenantScopedModel`

#### 6. MonthEndRun (Month-End Processing)
- **Purpose**: Monthly processing of vesting, sales, and tax directives
- **Key Fields**:
  - Period: period_year, period_month, title
  - Status: DRAFT → APPROVED → PROCESSING → COMPLETED/FAILED
  - Totals: total_shares_vested, total_gross_proceeds, total_tax
- **State Machine**: Same pattern as DividendRun
- **Relationships**:
  - Belongs to one Company
  - Has many VestingEvents, TaxDirectives
- **Inheritance**: Inherits from `TenantScopedModel`

#### 7. VestingEvent (Share Movement)
- **Purpose**: Tracks a beneficiary's share vesting, sale, or forfeiture
- **Key Fields**:
  - event_type: SCHEDULED, SALE, FORFEITURE, TRANSFER
  - shares_affected, shares_before, shares_after
  - share_price (for sales), gross/tax/net amounts
  - status: PENDING, PROCESSED, FAILED
- **Relationships**: Links MonthEndRun + Beneficiary
- **Inheritance**: Inherits from `TenantScopedModel`

#### 8. TaxDirective (SARS Compliance)
- **Purpose**: Tax directive from SARS for share transactions
- **Key Fields**:
  - directive_number (from SARS)
  - status: PENDING, REQUESTED, RECEIVED, DECLINED
  - taxable_amount, directive_rate, calculated_tax
- **Relationships**: Links MonthEndRun + Beneficiary
- **Inheritance**: Inherits from `TenantScopedModel`

#### 9. Document (File Storage)
- **Purpose**: Secure storage of scheme documents
- **Key Fields**:
  - file (FileField with custom upload path)
  - category: TRUST_DEED, TAX_CERTIFICATE, BENEFICIARY_ID, etc.
  - status: QUARANTINE → ACTIVE (after malware scan)
  - file_hash (SHA-256 for integrity)
- **Security**:
  - Files NOT served via MEDIA_URL
  - Download requires authentication and permission check
  - Uploaded to tenant-scoped path: `documents/{company_id}/{filename}`
- **Relationships**:
  - Belongs to one Company
  - Optionally linked to one Beneficiary
- **Inheritance**: Inherits from `TenantScopedModel`

#### 10. IntegrationLog (External API Tracking)
- **Purpose**: Audit trail for all external API calls
- **Key Fields**:
  - system: PAYROLL, SARS, JSE, BANKING
  - operation (e.g., "submit_tax_directive")
  - status: PENDING, IN_PROGRESS, SUCCESS, FAILED
  - request_data, response_data (sanitized)
  - retry_count, max_retries
- **Idempotency**: Has idempotency_key to prevent duplicate calls
- **Relationships**:
  - Belongs to one Company
  - References any related object (via reference_model + reference_id)
- **Inheritance**: Inherits from `TenantScopedModel`

#### 11. AuditLog (Immutable Audit Trail)
- **Purpose**: Compliance and forensic audit trail
- **Key Fields**:
  - user, ip_address, timestamp
  - action (from AuditAction.choices)
  - company, target_model, target_id
  - details (JSONB for flexible payload)
- **Immutability**: Cannot be updated or deleted (enforced in save/delete methods)
- **Indexes**: Multi-column indexes for fast filtering by company, user, action
- **Inheritance**: Direct from `models.Model` (NOT tenant-scoped, has its own company field)

#### 12. JSECompany (Reference Data)
- **Purpose**: Static list of JSE-listed companies
- **Key Fields**:
  - ticker (e.g., "SOL", "NPN")
  - company_name, isin, sector
  - share_price, market_cap (enriched from Yahoo Finance)
- **NOT Tenant-Scoped**: This is shared reference data
- **Relationships**: None (independent reference table)
- **Enrichment**: Celery task fetches live data from Yahoo Finance API

---

### Base Model Hierarchy

```
models.Model (Django)
    ↓ inherits
BaseModel (common.models)
    ├── id: UUIDField (primary key)
    ├── created_at: DateTimeField
    └── updated_at: DateTimeField

    ↓ inherits
TenantScopedModel (common.models)
    ├── company: ForeignKey(Company)
    └── objects: TenantScopedManager
        └── for_tenant(company) method
```

**All tenant-scoped models inherit from `TenantScopedModel`**:
- Beneficiary
- DividendRun
- DividendAllocation
- MonthEndRun
- VestingEvent
- TaxDirective
- Document
- IntegrationLog

**Models that inherit from `BaseModel` (not tenant-scoped)**:
- Company (the tenant itself)

**Models that inherit directly from `models.Model`**:
- User (has optional company FK, but can be null for admins)
- AuditLog (has company FK for filtering, but not tenant-scoped in the same way)
- JSECompany (reference data, no company relationship)

---

## Security Architecture

### 1. Multi-Tenant Isolation

**Goal**: Prevent Company A from accessing Company B's data.

**Mechanisms**:

1. **Queryset Filtering** (Application Layer):
   ```python
   # Every query MUST filter by company
   runs = DividendRun.objects.filter(company=request.user.company)

   # Or use the manager helper
   runs = DividendRun.objects.for_tenant(company)
   ```

2. **Object-Level Permissions** (DRF):
   ```python
   class TenantScopedPermission(BasePermission):
       def has_object_permission(self, request, view, obj):
           return request.user.can_access_company(obj.company)
   ```

3. **Perform Create Override** (DRF):
   ```python
   def perform_create(self, serializer):
       # Server-side enforcement: ignore company from request body
       serializer.save(
           company=self.request.user.company,
           created_by=self.request.user
       )
   ```

4. **URL-Based Scoping** (Web Views):
   ```python
   class MonthEndCompanyMixin:
       def dispatch(self, request, *args, **kwargs):
           self.company = get_object_or_404(Company, pk=kwargs["company_pk"])
           # Implicit: user must have access to this company
           return super().dispatch(request, *args, **kwargs)
   ```

**Database Constraints**:
- Foreign keys with `on_delete=PROTECT` prevent accidental deletion
- Unique constraints scoped by company (e.g., employee_number unique per company)

---

### 2. Data Encryption at Rest

**Goal**: Protect PII even if database is compromised.

**Encrypted Fields**:
- Beneficiary.id_number_encrypted (SA ID number)
- Beneficiary.account_number_encrypted (bank account)

**Implementation**:
```python
from cryptography.fernet import Fernet

def encrypt_value(plaintext: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.encrypt(plaintext.encode()).decode()

def decrypt_value(ciphertext: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.decrypt(ciphertext.encode()).decode()

# Model properties for transparent access
class Beneficiary(TenantScopedModel):
    id_number_encrypted = models.TextField()

    @property
    def id_number(self) -> str:
        return decrypt_value(self.id_number_encrypted)

    @id_number.setter
    def id_number(self, value: str):
        self.id_number_encrypted = encrypt_value(value)
```

**Key Management**:
- `ENCRYPTION_KEY` stored in environment variable (not in code)
- Production: Use key management service (AWS KMS, Azure Key Vault)

---

### 3. Authentication & Authorization

**Authentication Backends**:
- Session-based (web interface): Django's default session backend
- Token-based (API): Django REST Framework's TokenAuthentication

**Custom Backend**:
```python
class LockoutBackend(ModelBackend):
    """Custom backend with account lockout after failed attempts."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = User.objects.get(username=username)

        # Check if account is locked
        if user.locked_until and timezone.now() < user.locked_until:
            raise PermissionDenied("Account is locked")

        # Attempt authentication
        if user.check_password(password):
            user.failed_login_attempts = 0
            user.save()
            return user
        else:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = timezone.now() + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
            user.save()
            return None
```

**Authorization**:

**Role-Based Access Control (RBAC)**:
```python
class UserRole(models.TextChoices):
    SCHEME_ADMIN = "scheme_admin"  # Internal staff, cross-company access
    BENEFICIARY = "beneficiary"     # External portal users, single company
```

**Permission Classes** (DRF):
- `IsAuthenticated`: Must be logged in
- `IsSchemeAdmin`: User role must be SCHEME_ADMIN
- `IsBeneficiary`: User role must be BENEFICIARY
- `IsSchemeAdminOrReadOnly`: Read for all, write for scheme admin only
- `IsOwnerOrSchemeAdmin`: Object owner or scheme admin
- `TenantScopedPermission`: Object belongs to user's company

**Permission Flow**:
```
Request
  ↓
Authentication (session or token)
  ↓
has_permission() (view-level)
  ↓
get_queryset() (tenant scoping)
  ↓
get_object() (retrieve object)
  ↓
has_object_permission() (object-level)
  ↓
Action permitted
```

---

### 4. CSRF Protection

**Web Interface**: Django's CSRF middleware (enabled by default)
- All POST requests from web forms require CSRF token
- Token embedded in forms via `{% csrf_token %}`

**API Interface**:
- **Token authentication**: No CSRF (tokens are not in cookies)
- **Session authentication**: CSRF required (cookie-based, vulnerable to CSRF)

**Configuration**:
```python
MIDDLEWARE = [
    # ...
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF protection
    # ...
]

# DRF settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}
```

---

### 5. Secure File Handling

**Upload Validation**:
1. File type allowlist (not blocklist)
2. Magic bytes validation (not just extension)
3. File size limits
4. Virus scanning (status = QUARANTINE until scanned)

**Storage**:
```python
def get_upload_path(instance, filename):
    # Sanitize filename
    safe_name = sanitize_filename(filename)
    # Tenant-scoped path
    return f"documents/{instance.company.id}/{safe_name}"
```

**Download Security**:
```python
# Documents are NEVER served via MEDIA_URL
# All downloads go through authenticated view

class DocumentDownloadView(View):
    def get(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)

        # Permission check
        if not request.user.can_access_company(doc.company):
            raise PermissionDenied

        # Status check
        if not doc.is_accessible:
            raise Http404

        # Stream file with correct headers
        response = FileResponse(doc.file, content_type=doc.content_type)
        response["Content-Disposition"] = f'attachment; filename="{doc.original_filename}"'
        return response
```

---

### 6. Security Middleware

**TenantMiddleware**:
- Attaches current company to request object (for web views)
- Used by views to scope queries

**AdminIPAllowlistMiddleware**:
- Restricts Django admin access to whitelisted IP addresses
- Production: Only office IPs or VPN

**Order matters**:
```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.TenantMiddleware",             # Custom
    "common.middleware.AdminIPAllowlistMiddleware",   # Custom
]
```

---

### 7. Security Headers

**Configured in settings**:
```python
# Prevent clickjacking
X_FRAME_OPTIONS = "DENY"

# Force HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Prevent MIME sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True

# XSS protection
SECURE_BROWSER_XSS_FILTER = True

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

---

## Application Layer

### Web Interface (Class-Based Views)

**Purpose**: Server-rendered HTML for scheme admins (internal staff).

**Technology**: Django CBVs + templates + HTMX

**URL Pattern**:
```
/companies/<company_pk>/month-end-runs/
/companies/<company_pk>/month-end-runs/<pk>/
/companies/<company_pk>/month-end-runs/<pk>/approve/
```

**Example View**:
```python
class MonthEndRunListView(MonthEndCompanyMixin, ListView):
    model = MonthEndRun
    template_name = "month_end/run_list.html"

    def get_queryset(self):
        # Scoped by company from URL
        return MonthEndRun.objects.for_tenant(self.company)
```

**State Change View**:
```python
class MonthEndRunApproveView(MonthEndCompanyMixin, View):
    def post(self, request, company_pk, pk):
        run = get_object_or_404(MonthEndRun, pk=pk, company=self.company)

        try:
            # Call service layer
            approve_run(run, request.user)
            messages.success(request, "Run approved successfully")
        except InvalidStateTransitionError as e:
            messages.error(request, str(e))

        return redirect("month-end-run-detail", company_pk=company_pk, pk=pk)
```

**Template Pattern** (HTMX for partial updates):
```html
<!-- month_end/run_list.html -->
<table id="run-table">
  {% for run in runs %}
    <tr>
      <td>{{ run.title }}</td>
      <td>
        <a href="{% url 'month-end-run-detail' company_pk=company.pk pk=run.pk %}"
           hx-get="{% url 'month-end-run-detail' company_pk=company.pk pk=run.pk %}"
           hx-target="#main-content">
          View
        </a>
      </td>
    </tr>
  {% endfor %}
</table>
```

---

### API Interface (Django REST Framework)

**Purpose**: JSON API for mobile apps, integrations, and beneficiary portal.

**Technology**: DRF ViewSets + Serializers

**URL Pattern**:
```
/api/v1/dividend-runs/
/api/v1/dividend-runs/<pk>/
/api/v1/dividend-runs/<pk>/approve/
```

**ViewSet Example**:
```python
class DividendRunViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DividendRun.objects.all()
    serializer_class = DividendRunSerializer
    permission_classes = [IsAuthenticated, TenantScopedPermission]

    # Override queryset to scope by user's company
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(company=self.request.user.company)

    # Custom action (not CRUD)
    @action(detail=True, methods=["post"], permission_classes=[IsSchemeAdmin])
    def approve(self, request, pk=None):
        run = self.get_object()

        with transaction.atomic():
            try:
                approve_run(run, request.user)
                return Response({"message": "Run approved successfully"})
            except InvalidStateTransitionError as e:
                return Response({"error": str(e)}, status=400)
```

**Custom Exception Handler**:
```python
def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        # Standardize error format
        response.data = {
            "error": {
                "code": _get_error_code(exc),
                "message": str(exc),
                "details": getattr(exc, "detail", None),
            }
        }

    return response
```

**Error Response Format**:
```json
{
  "error": {
    "code": "invalid_state_transition",
    "message": "Cannot transition from COMPLETED to APPROVED",
    "details": null
  }
}
```

---

### Service Layer (Business Logic)

**Purpose**: Encapsulate complex business rules, state machines, and workflows.

**Location**: `apps/{app_name}/services.py`

**Key Functions**:

1. **State Transitions**:
   - `approve_run(run, user)`: Move to APPROVED
   - `process_run(run)`: Move to PROCESSING, create allocations, then COMPLETED
   - `reset_to_draft(run)`: Delete allocations and reset to DRAFT

2. **Business Rules**:
   - Four-eyes approval (creator ≠ approver)
   - State machine validation
   - Idempotency guards

3. **Data Operations**:
   - Create allocations (idempotent)
   - Compute totals (aggregations)
   - Generate payment files

**Transaction Handling**:
```python
@transaction.atomic()
def process_run(run: DividendRun) -> DividendRun:
    # All changes succeed or all fail
    _validate_transition(run, RunStatus.PROCESSING)
    _change_status(run, RunStatus.PROCESSING)

    try:
        _create_allocations(run)
        _compute_totals(run)
        _change_status(run, RunStatus.COMPLETED)
    except Exception as e:
        run.failure_reason = str(e)
        _change_status(run, RunStatus.FAILED)
        raise

    return run
```

**Idempotency Pattern**:
```python
def _create_allocations(run: DividendRun):
    # Guard: skip if already created
    if DividendAllocation.objects.filter(run=run).exists():
        logger.info(f"Allocations already exist for run {run.pk}")
        return

    # Fetch active beneficiaries
    beneficiaries = Beneficiary.objects.filter(
        company=run.company,
        status=BeneficiaryStatus.ACTIVE
    )

    # Bulk create
    allocations = [
        DividendAllocation(
            run=run,
            beneficiary=b,
            shares_at_record_date=b.vested_shares,
            gross_amount=b.vested_shares * run.dividend_per_share,
            # ... calculate tax and net
        )
        for b in beneficiaries
    ]
    DividendAllocation.objects.bulk_create(allocations)
```

---

## Integration Architecture

### External Systems

The platform integrates with:

1. **SARS (South African Revenue Service)**
   - Submit tax directives
   - Retrieve tax rates and certificates

2. **JSE (Johannesburg Stock Exchange)**
   - Fetch share prices
   - Retrieve dividend announcements

3. **Yahoo Finance**
   - Enrich JSE company data with live prices

4. **Banking APIs**
   - Generate EFT/NAEDO payment files
   - Submit bulk payments

5. **Payroll Systems**
   - Sync employee data
   - Submit payroll deductions

### Integration Pattern

**Async Processing** (Celery):
```python
@shared_task
def enrich_jse_company_data(company_id):
    """Fetch live data from Yahoo Finance."""
    company = JSECompany.objects.get(pk=company_id)

    # Create integration log
    log = IntegrationLog.objects.create(
        system=IntegrationSystem.JSE,
        operation="enrich_company_data",
        status=IntegrationStatus.IN_PROGRESS,
        reference_model="JSECompany",
        reference_id=str(company_id),
    )

    try:
        # Call external API
        data = fetch_from_yahoo_finance(company.yahoo_ticker)

        # Update company
        company.share_price = data["price"]
        company.market_cap = data["market_cap"]
        company.last_enriched_at = timezone.now()
        company.save()

        # Update log
        log.status = IntegrationStatus.SUCCESS
        log.response_data = data
        log.completed_at = timezone.now()
        log.save()

    except Exception as e:
        log.status = IntegrationStatus.FAILED
        log.error_message = str(e)
        log.save()
        raise
```

**Retry Logic**:
```python
@shared_task(bind=True, max_retries=3)
def submit_tax_directive(self, directive_id):
    try:
        # ... submit to SARS
        pass
    except Exception as e:
        # Exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 60)
```

**Idempotency**:
```python
def call_external_api(operation, idempotency_key, **kwargs):
    # Check if already called
    existing = IntegrationLog.objects.filter(
        idempotency_key=idempotency_key,
        status=IntegrationStatus.SUCCESS
    ).first()

    if existing:
        return existing.response_data

    # Create log and proceed
    # ...
```

---

## Data Flow Patterns

### 1. Dividend Distribution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CREATE (DRAFT)                                                │
│    Scheme admin creates DividendRun with:                        │
│    - total_amount, dividend_per_share, record_date               │
│    Status: DRAFT                                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. APPROVE                                                       │
│    Different scheme admin calls approve_run()                    │
│    - Validates four-eyes rule (creator ≠ approver)               │
│    - Updates status to APPROVED                                  │
│    - Logs audit entry                                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. PROCESS (Atomic Transaction)                                 │
│    Scheme admin calls process_run()                              │
│    - Status → PROCESSING                                         │
│    - For each ACTIVE beneficiary:                                │
│      - Create DividendAllocation                                 │
│      - Calculate gross = shares × dividend_per_share             │
│      - Calculate tax = gross × dwt_rate                          │
│      - Calculate net = gross - tax                               │
│    - Compute run totals (aggregate allocations)                  │
│    - Status → COMPLETED                                          │
│    - If error: Status → FAILED, save failure_reason              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. PAYMENT FILE GENERATION                                       │
│    System generates EFT file for banking:                        │
│    - One row per allocation                                      │
│    - Beneficiary bank details (decrypted)                        │
│    - Net amount                                                  │
│    - Payment reference                                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. PAYMENT SUBMISSION                                            │
│    Integration with banking API:                                 │
│    - Submit payment file                                         │
│    - Track submission in IntegrationLog                          │
│    - Update allocation status to PAID on success                 │
└─────────────────────────────────────────────────────────────────┘
```

**Rollback Scenario**:
```
PROCESSING
  ↓ (allocation creation fails)
transaction.atomic() rolls back all changes
  ↓
Status remains APPROVED (unchanged)
```

---

### 2. Month-End Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CREATE (DRAFT)                                                │
│    Scheme admin creates MonthEndRun for period (e.g., Jan 2025) │
│    - Idempotency key prevents duplicate months                  │
│    Status: DRAFT                                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. APPROVE                                                       │
│    Different user approves (four-eyes)                           │
│    Status: APPROVED                                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. PROCESS (Atomic Transaction)                                 │
│    Input: share_price, tax_rate                                  │
│    Status: PROCESSING                                            │
│                                                                  │
│    For each beneficiary:                                         │
│    a) Scheduled vesting (if any):                                │
│       - Calculate vested_shares based on vesting schedule        │
│       - Create VestingEvent (type=SCHEDULED)                     │
│       - Update Beneficiary.vested_shares                         │
│                                                                  │
│    b) Share sale (if triggered):                                 │
│       - Calculate gross = shares × share_price                   │
│       - Calculate tax = gross × tax_rate                         │
│       - Calculate net = gross - tax                              │
│       - Create VestingEvent (type=SALE)                          │
│       - Update Beneficiary.vested_shares (reduce)                │
│                                                                  │
│    c) Tax directive (if required):                               │
│       - Create TaxDirective (status=PENDING)                     │
│       - Queue Celery task to submit to SARS                      │
│                                                                  │
│    d) Compute run totals                                         │
│    e) Status → COMPLETED                                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. POST-PROCESSING                                               │
│    - Generate month-end report (PDF)                             │
│    - Store as Document (category=MONTH_END_REPORT)               │
│    - Send email notifications to beneficiaries                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3. API Request Flow

```
HTTP Request (e.g., POST /api/v1/dividend-runs/123/approve/)
  ↓
1. Django URL Routing
  ↓
2. DRF Router → DividendRunViewSet.approve()
  ↓
3. Authentication
   - Check Authorization header for token
   - Or check session cookie
   - Reject if neither (401)
  ↓
4. View-Level Permission (has_permission)
   - IsSchemeAdmin.has_permission(request, view)
   - Check user.role == SCHEME_ADMIN
   - Deny if not (403)
  ↓
5. Get Object
   - ViewSet calls get_queryset() (tenant scoping)
   - Retrieves object with pk=123
   - Raises 404 if not found in scoped queryset
  ↓
6. Object-Level Permission (has_object_permission)
   - TenantScopedPermission.has_object_permission(request, view, obj)
   - Check obj.company == user.company
   - Deny if not (403)
  ↓
7. Action Logic
   - Call service layer: approve_run(run, request.user)
   - Service validates four-eyes rule
   - Service validates state transition
   - Service updates status, logs audit
  ↓
8. Serialization
   - Convert run to JSON via DividendRunSerializer
  ↓
9. Response
   - Return 200 with {"message": "Run approved successfully"}
   - Or 400/403 with error envelope
```

---

## Scalability and Performance

### Database Optimizations

**Indexes**:
```python
class Meta:
    indexes = [
        models.Index(fields=["company", "status"]),
        models.Index(fields=["company", "period_year", "period_month"]),
    ]
```

**Composite Indexes**:
- company + status (for filtering runs by company and status)
- company + period (for preventing duplicate month-end runs)

**Select Related / Prefetch Related**:
```python
# Avoid N+1 queries
runs = DividendRun.objects.select_related(
    "company", "created_by", "approved_by"
).prefetch_related("allocations__beneficiary")
```

**Bulk Operations**:
```python
# Avoid individual saves
DividendAllocation.objects.bulk_create(allocations)
```

**Aggregation**:
```python
# Use database for computation
totals = DividendAllocation.objects.filter(run=run).aggregate(
    total_gross=Sum("gross_amount"),
    total_tax=Sum("tax_amount"),
    total_net=Sum("net_amount"),
)
```

---

### Caching Strategy

**Query Result Caching** (potential):
```python
from django.core.cache import cache

def get_active_beneficiaries(company):
    cache_key = f"beneficiaries:active:{company.id}"
    result = cache.get(cache_key)

    if result is None:
        result = list(Beneficiary.objects.filter(
            company=company,
            status=BeneficiaryStatus.ACTIVE
        ))
        cache.set(cache_key, result, timeout=300)  # 5 minutes

    return result
```

**Invalidation**:
```python
# Invalidate on beneficiary status change
def update_beneficiary_status(beneficiary, new_status):
    beneficiary.status = new_status
    beneficiary.save()

    # Invalidate cache
    cache.delete(f"beneficiaries:active:{beneficiary.company.id}")
```

---

### Background Processing (Celery)

**Use Cases**:
- Integration API calls (SARS, JSE, banking)
- Report generation (PDF, Excel)
- Email notifications (bulk sends)
- Data enrichment (Yahoo Finance)

**Task Example**:
```python
@shared_task
def generate_month_end_report(run_id):
    run = MonthEndRun.objects.get(pk=run_id)

    # Heavy computation
    pdf = generate_pdf_report(run)

    # Save as document
    doc = Document.objects.create(
        company=run.company,
        title=f"Month-End Report - {run.title}",
        category=DocumentCategory.MONTH_END_REPORT,
        file=pdf,
        uploaded_by=run.created_by,
    )

    return doc.id
```

**Task Queue Architecture**:
```
Django App
  ↓ enqueues task
Celery Broker (Redis/RabbitMQ)
  ↓ picks up task
Celery Worker
  ↓ executes
  - Generates report
  - Calls external API
  - Sends emails
  ↓ updates
Django DB (results)
```

---

### Horizontal Scaling

**Stateless Application**:
- No session data stored in app memory (uses DB-backed sessions)
- Enables multiple app servers behind load balancer

**Database Connection Pooling**:
```python
DATABASES["default"]["CONN_MAX_AGE"] = 60  # Reuse connections
```

**Load Balancer Configuration**:
```
┌──────────────┐
│ Load Balancer│
└──────┬───────┘
       │
       ├─────► App Server 1 (Gunicorn)
       ├─────► App Server 2 (Gunicorn)
       └─────► App Server 3 (Gunicorn)
            │
            ▼
       ┌──────────┐
       │ Postgres │
       │  (Primary)│
       └────┬─────┘
            │
       ┌────▼─────┐
       │ Postgres │
       │ (Replica)│
       └──────────┘
```

---

## Summary

This ESOP platform is a **secure, compliant, multi-tenant Django application** with:

1. **Strong tenant isolation**: Row-level security enforced at application and DB levels
2. **Encrypted PII**: ID numbers and bank accounts encrypted at rest
3. **Immutable audit trail**: All sensitive actions logged, cannot be modified
4. **State machine workflows**: Dividend and month-end processing follow defined states
5. **Service layer pattern**: Business logic centralized, reusable across web and API
6. **Two interfaces**: HTML (admins) and JSON API (beneficiaries, integrations)
7. **External integrations**: SARS, JSE, banking via logged async tasks
8. **Scalable design**: Optimized queries, caching, background tasks, horizontal scaling

The architecture balances **security** (encryption, isolation, auditing) with **usability** (two interfaces, clear workflows) and **compliance** (four-eyes approval, state machines, tax calculations).

---

**End of Document**
