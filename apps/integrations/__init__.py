"""
Integrations app - External system integration clients and logging.

Provides stub implementations for:
- Payroll API (employee data sync)
- SARS e-Filing (tax directives)
- Velocity Trade (share sales via JSE)
- Banking (EFT/NAEDO payments)
"""

default_app_config = "apps.integrations.apps.IntegrationsConfig"

