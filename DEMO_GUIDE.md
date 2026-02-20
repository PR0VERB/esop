# ESOP Platform — CEO Demo Guide
**Ubuntu Industrial Holdings (Pty) Ltd | February 2026**

> All names, numbers, and registration details are fictional demo data.
> This is not financial or tax advice.

---

## 1. Before You Start

```bash
# From the project root, activate the venv and start the server
esopEnv/Scripts/activate
python manage.py runserver
```

Then open **http://localhost:8000** in your browser.

---

## 2. Login Credentials

| | User 1 — Primary Admin | User 2 — Approver |
|---|---|---|
| **Username** | `ubuntu_admin` | `ubuntu_approver` |
| **Password** | `ESOP_Admin@2026` | `ESOP_Appr0ver@26` |
| **Name** | Nomsa Dube | Kagiso Sithole |
| **Role** | Scheme Admin | Scheme Admin |
| **Use for** | Creating, navigating, processing | Approving runs (four-eyes) |

Login URL: **http://localhost:8000/accounts/login/**

> **MFA is disabled** in the dev environment — no TOTP step required.

---

## 3. The Demo Company (Tenant)

| Field | Value |
|---|---|
| Company name | Ubuntu Industrial Holdings (Pty) Ltd |
| CIPC registration | 2010/012345/07 |
| SARS income tax # | 9876543210 |
| Scheme name | Ubuntu ESOP Trust |
| Trust name | Ubuntu Employee Share Trust |
| Trust bank account | 000123456789 (demo) |
| **Company UUID** | `21a1dcc8-50e8-49c4-ad61-64607ada7665` |

---

## 4. Beneficiary Register

| Emp # | Name | Status | Total | Vested | Unvested | Bank | Eligible? |
|---|---|---|---|---|---|---|---|
| EMP-1001 | Zinhle Dlamini | Active | 1,200 | 300 | 900 | Standard Bank | Yes |
| EMP-1002 | Thabo Mokoena | Active | 2,000 | 800 | 1,200 | FNB | Yes |
| EMP-1003 | Aisha Patel | Active | 1,500 | 500 | 1,000 | Nedbank | Yes |
| EMP-1004 | Pieter van Wyk | Active | 500 | **0** | 500 | Absa | **No** — vested = 0 |
| EMP-1005 | Lerato Ncube | **Terminated** | 1,000 | 200 | 800 | Capitec | **No** — not active |
| EMP-1006 | Sipho Khumalo | Active | 1,800 | 600 | 1,200 | Standard Bank | Yes |

**Eligible total vested shares: 2,200** (EMP-1001 + EMP-1002 + EMP-1003 + EMP-1006)

> SA ID numbers are intentionally blank — safe for screen-share and video demos (POPIA).
> Bank account numbers are fictional and stored **encrypted at rest** (Fernet/AES).

---

## 5. Demo URLs

Replace `<COMPANY>` with `21a1dcc8-50e8-49c4-ad61-64607ada7665` — or use the links below directly.

### 5.1 Companies

| Page | URL |
|---|---|
| Company list | http://localhost:8000/companies/ |
| Ubuntu Holdings detail | http://localhost:8000/companies/21a1dcc8-50e8-49c4-ad61-64607ada7665/ |

### 5.2 Beneficiaries

| Page | URL |
|---|---|
| Beneficiary register | http://localhost:8000/beneficiaries/21a1dcc8-50e8-49c4-ad61-64607ada7665/ |
| Zinhle Dlamini | http://localhost:8000/beneficiaries/21a1dcc8-50e8-49c4-ad61-64607ada7665/4cd1fdf2-606b-4848-9e33-a101a22611ee/ |
| Thabo Mokoena | http://localhost:8000/beneficiaries/21a1dcc8-50e8-49c4-ad61-64607ada7665/526dfe50-2471-430f-9192-d3b11b1698d2/ |
| Aisha Patel | http://localhost:8000/beneficiaries/21a1dcc8-50e8-49c4-ad61-64607ada7665/c9fdb25d-c483-45e8-bcc6-7f69c48ce78f/ |
| Pieter van Wyk | http://localhost:8000/beneficiaries/21a1dcc8-50e8-49c4-ad61-64607ada7665/d603cc69-1023-4d4b-86a1-2ff4238b9fa3/ |
| Lerato Ncube (Terminated) | http://localhost:8000/beneficiaries/21a1dcc8-50e8-49c4-ad61-64607ada7665/8ac1b6ae-1189-4f61-abf0-1768059354c5/ |
| Sipho Khumalo | http://localhost:8000/beneficiaries/21a1dcc8-50e8-49c4-ad61-64607ada7665/153a2c09-fda2-44db-b714-712ac96ce79e/ |

### 5.3 Documents

| Page | URL |
|---|---|
| Document vault | http://localhost:8000/documents/21a1dcc8-50e8-49c4-ad61-64607ada7665/ |

### 5.4 Dividends

| Page | URL |
|---|---|
| Dividend runs list | http://localhost:8000/dividends/21a1dcc8-50e8-49c4-ad61-64607ada7665/ |
| **FY2026 Interim Dividend (DRAFT)** | http://localhost:8000/dividends/21a1dcc8-50e8-49c4-ad61-64607ada7665/6534bba3-5a7f-4345-aa89-64451f221549/ |

### 5.5 Month-End

| Page | URL |
|---|---|
| Month-end runs list | http://localhost:8000/month-end/21a1dcc8-50e8-49c4-ad61-64607ada7665/ |
| **February 2026 Month-End (DRAFT)** | http://localhost:8000/month-end/21a1dcc8-50e8-49c4-ad61-64607ada7665/7d516311-0354-48ce-86b9-0123fb0c2689/ |

### 5.6 Audit Log (Django Admin)

| Page | URL |
|---|---|
| Audit log (immutable) | http://localhost:8000/admin/audit/auditlog/ |

---

## 6. Dividend Run — Expected Numbers

**Run:** FY2026 Interim Dividend (Demo) | **Status:** DRAFT

| Input | Value |
|---|---|
| Dividend per share | R12.50 |
| DWT rate | 20% (0.2000) |
| Record date | 13 February 2026 |
| Payment date | 20 February 2026 |
| Declaration date | 10 February 2026 |

| Output | Value |
|---|---|
| Eligible shares | 2,200 |
| **Total gross** | **R27,500.00** |
| **Total DWT (20%)** | **R5,500.00** |
| **Total net** | **R22,000.00** |
| Allocations | 4 |

**Per-beneficiary breakdown:**

| Beneficiary | Vested shares | Gross | DWT (20%) | Net |
|---|---|---|---|---|
| Zinhle Dlamini | 300 | R3,750.00 | R750.00 | R3,000.00 |
| Thabo Mokoena | 800 | R10,000.00 | R2,000.00 | R8,000.00 |
| Aisha Patel | 500 | R6,250.00 | R1,250.00 | R5,000.00 |
| Sipho Khumalo | 600 | R7,500.00 | R1,500.00 | R6,000.00 |
| **Total** | **2,200** | **R27,500.00** | **R5,500.00** | **R22,000.00** |

---

## 7. Month-End Run — Expected Numbers

**Run:** February 2026 Month-End | **Status:** DRAFT

| Input | Value |
|---|---|
| Period | February 2026 |
| Share price | R150.00 |
| Tax rate (Section 8C) | 35% (0.3500) |

| Output | Value |
|---|---|
| Eligible shares | 2,200 |
| **Total gross proceeds** | **R330,000.00** |
| **Total tax (35%)** | **R115,500.00** |
| **Total net proceeds** | **R214,500.00** |
| Vesting events | 4 |

**Per-beneficiary breakdown:**

| Beneficiary | Shares | Gross | Tax (35%) | Net |
|---|---|---|---|---|
| Zinhle Dlamini | 300 | R45,000.00 | R15,750.00 | R29,250.00 |
| Thabo Mokoena | 800 | R120,000.00 | R42,000.00 | R78,000.00 |
| Aisha Patel | 500 | R75,000.00 | R26,250.00 | R48,750.00 |
| Sipho Khumalo | 600 | R90,000.00 | R31,500.00 | R58,500.00 |
| **Total** | **2,200** | **R330,000.00** | **R115,500.00** | **R214,500.00** |

---

## 8. Four-Eyes Approval Workflow

The system **enforces** that the approver must be a different user from the creator.
Attempting to approve your own run will return an error.

```
ubuntu_admin    = Creator  (created both DRAFT runs)
ubuntu_approver = Approver (must be used to approve)
```

### Step-by-step

**Step 1 — Log in as ubuntu_admin**
- Navigate to the dividend run or month-end run detail page
- Confirm the run is in **DRAFT** status with your numbers visible

**Step 2 — Log out → log in as ubuntu_approver**
- Open the same run detail URL
- Click **Approve**
- Run moves to **APPROVED**
- System records: approved_by = Kagiso Sithole, approved_at = [timestamp]

**Step 3 — Click Process** (either user can do this)
- Allocations / vesting events are created from the live beneficiary register
- Run moves to **COMPLETED**
- Totals are computed and locked

**Step 4 — Open the audit log**
- URL: http://localhost:8000/admin/audit/auditlog/
- Every state change is timestamped, user-attributed, and **immutable** (no edit/delete in the UI)

> **To reset a run back to DRAFT** (if you want to demo the workflow again):
> Click **Reset to Draft** on the run detail page. This deletes the allocations/events
> so the workflow can be re-run cleanly.

---

## 9. SA Tax Terms — Talk Track

| Term | What to say |
|---|---|
| **DWT** | "Dividends Withholding Tax — SARS requires us to withhold 20% at source before paying beneficiaries. The platform calculates and records this automatically." |
| **Section 8C** | "When shares vest or are disposed of, SARS treats this as income. The 35% rate here represents the tax directive rate we'd apply on the gain." |
| **SARS tax directive** | "For larger disposals, we'd request a directive from SARS specifying the applicable rate. The platform has a workflow to log directive requests, track responses, and apply the approved rate." |
| **PAYE / IRP5** | "The net payment figures feed into payroll for IRP5 reporting — the platform produces the data extract your payroll team needs." |
| **POPIA** | "All SA ID numbers and bank account details are encrypted at rest using AES/Fernet. The audit log records every access event for POPIA compliance." |
| **JSE / SENS** | "For JSE-listed companies, the platform auto-fills ticker, ISIN, and sector from a live JSE reference dataset using the search widget on the company form." |

---

## 10. Key Architecture Points (for technical questions)

| Topic | Detail |
|---|---|
| Multi-tenancy | Every data row is scoped to a `company_id` — no data can cross tenant boundaries |
| Encryption | SA ID numbers and bank account numbers are encrypted with Fernet (AES-128) — not readable in the database |
| State machine | DRAFT → APPROVED → PROCESSING → COMPLETED (or FAILED). Transitions are enforced in the service layer, not the UI |
| Four-eyes | Hardcoded in the service: `if user == run.created_by: raise InvalidStateTransition` |
| Idempotency | Each run has a unique `idempotency_key` — duplicate processing is a no-op |
| Audit trail | Every create, update, and state change writes an `AuditLog` row. The admin marks it read-only and prevents delete |
| Currency | All amounts stored as `DecimalField` — no floats, no rounding errors |

---

*Generated: 20 February 2026 | Demo environment only — do not use in production*
