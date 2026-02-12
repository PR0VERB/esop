# ESOP Platform — TODO (Urgent → Later)

This list captures the most important UX + security gaps discovered during review.

## P0 — Must fix before real users / production

- [ ] Replace MFA stub with real TOTP verification (`apps/accounts/views.py`) and add enrollment/disable flows; do not accept arbitrary 6-digit tokens.
- [ ] Encrypt or otherwise protect `mfa_secret` at rest (currently plaintext in `apps/accounts/models.py`) and prevent it from being viewable/editable in cleartext.
- [ ] Fix potential cross-beneficiary data exposure in API list endpoints for allocations/events when a beneficiary user lacks `beneficiary_profile` (filters are conditional) (`apps/api/views.py`).
- [ ] Enforce CSP headers: `django-csp` is installed and `CONTENT_SECURITY_POLICY` exists, but CSP middleware is not enabled (`config/settings/base.py`).
- [ ] Add token lifecycle controls for API auth (expiry/rotation/revocation). DRF authtokens are effectively long-lived (`apps/api/urls.py`).

## P1 — High impact correctness / reliability

- [ ] Validate and coerce `share_price`/`tax_rate` in month-end API `process` to `Decimal` (and return consistent 400s on invalid input) (`apps/api/views.py`).
- [ ] Fix serializer/model field mismatches for vesting events + tax directives (serializers reference non-existent fields) (`apps/api/serializers.py`, `apps/month_end/models.py`).
- [ ] Add API-side validations that currently exist only in forms:
  - SA ID + bank account validation (`apps/beneficiaries/forms.py` vs `apps/api/serializers.py`)
  - Share totals consistency (`apps/beneficiaries/forms.py`)
  - Dividend date ordering (`apps/dividends/forms.py` vs `apps/api/serializers.py`)

## P2 — UX gaps that will frustrate users

- [ ] Add a post-login landing route (login redirects to `/` but no root URL is defined) (`config/settings/base.py`, `config/urls.py`).
- [ ] Move long-running workflow actions off request/response where appropriate (dividend/month-end processing currently runs synchronously in web views) (`apps/dividends/views.py`, `apps/month_end/views.py`).
- [ ] Add UI screens for audit logs + integration logs (currently admin-only via Django admin) (`apps/audit/admin.py`, `apps/integrations/admin.py`).
- [ ] Implement beneficiary portal UI (allocations, vesting events, documents) (see `FUNCTIONALITY_GUIDE.md`).

## P3 — Operational hardening / compliance hygiene

- [ ] Implement audit log retention pruning command referenced by the model (`apps/audit/models.py`).
- [ ] Harden client IP handling: avoid trusting `HTTP_X_FORWARDED_FOR` unless behind trusted proxies; document required proxy config (`common/middleware.py`).
- [ ] Encrypt sensitive tenant banking details (e.g., `trust_bank_account`) (`apps/tenants/models.py`).
- [ ] Replace in-memory per-process rate limiting with shared storage (Redis) for production consistency (`common/decorators.py`).

