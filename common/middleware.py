"""
Security middleware for the ESOP platform.
"""

import ipaddress
import logging

from django.conf import settings
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    Sets request.tenant based on the authenticated user's company.
    Scheme admins get tenant=None (access all), beneficiaries get their company.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        if hasattr(request, "user") and request.user.is_authenticated:
            if request.user.is_beneficiary:
                request.tenant = request.user.company
            # Scheme admins: tenant is None (all-access)
            # Views must still scope queries explicitly
        return self.get_response(request)


class AdminIPAllowlistMiddleware:
    """
    Restrict admin endpoints to specific IP addresses.
    Only enforced if ADMIN_IP_ALLOWLIST is non-empty.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowlist = self._parse_allowlist()

    def _parse_allowlist(self):
        raw = getattr(settings, "ADMIN_IP_ALLOWLIST", [])
        networks = []
        for cidr in raw:
            cidr = cidr.strip()
            if cidr:
                try:
                    networks.append(ipaddress.ip_network(cidr, strict=False))
                except ValueError:
                    logger.warning("Invalid CIDR in ADMIN_IP_ALLOWLIST: %s", cidr)
        return networks

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def __call__(self, request):
        if self.allowlist and request.path.startswith("/admin/"):
            client_ip = self._get_client_ip(request)
            try:
                ip = ipaddress.ip_address(client_ip)
                if not any(ip in network for network in self.allowlist):
                    logger.warning("Admin access denied from IP: %s", client_ip)
                    return HttpResponseForbidden("Access denied.")
            except ValueError:
                logger.warning("Could not parse client IP: %s", client_ip)
                return HttpResponseForbidden("Access denied.")
        return self.get_response(request)


def get_client_ip(request) -> str | None:
    """Utility to extract client IP from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

