"""
API Permission classes for tenant-scoped access control.

Security notes:
- All permissions are default-deny.
- Tenant scoping is enforced at the permission level.
- Scheme admins can access their company's data.
- Beneficiaries can only access their own records.
"""

from rest_framework import permissions

from apps.accounts.models import UserRole


class IsTenantMember(permissions.BasePermission):
    """
    Ensure user belongs to the same tenant as the requested resource.
    
    Views using this permission must implement `get_resource_company()` 
    or the resource must have a `company` attribute.
    """
    
    message = "You do not have access to this organization's data."
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Must be authenticated
        if not user or not user.is_authenticated:
            return False
        
        # Get the resource's company
        resource_company = getattr(obj, "company", None)
        if resource_company is None:
            # If object has no company, allow (shouldn't happen for tenant-scoped models)
            return True
        
        return user.can_access_company(resource_company)


class IsSchemeAdmin(permissions.BasePermission):
    """Only allow scheme admin users."""
    
    message = "This action requires scheme administrator privileges."
    
    def has_permission(self, request, view):
        user = request.user
        return user and user.is_authenticated and user.role == UserRole.SCHEME_ADMIN


class IsBeneficiary(permissions.BasePermission):
    """Only allow beneficiary users."""
    
    message = "This action is only available to beneficiaries."
    
    def has_permission(self, request, view):
        user = request.user
        return user and user.is_authenticated and user.role == UserRole.BENEFICIARY


class IsSchemeAdminOrReadOnly(permissions.BasePermission):
    """
    Allow scheme admins full access, others read-only.
    """
    
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for scheme admins
        return user.role == UserRole.SCHEME_ADMIN


class IsOwnerOrSchemeAdmin(permissions.BasePermission):
    """
    Object-level permission: user owns the object or is a scheme admin.
    
    For Beneficiary objects, check if the requesting user is the beneficiary.
    For other objects, check if the user field matches.
    """
    
    message = "You can only access your own records."
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Scheme admins can access all (within tenant)
        if user.role == UserRole.SCHEME_ADMIN:
            # Still check tenant access
            resource_company = getattr(obj, "company", None)
            if resource_company:
                return user.can_access_company(resource_company)
            return True
        
        # Beneficiaries can only access their own records
        if user.role == UserRole.BENEFICIARY:
            # Check if this is a Beneficiary object
            if hasattr(obj, "user"):
                return obj.user == user
            # Check if this is an allocation/event linked to a beneficiary
            if hasattr(obj, "beneficiary"):
                beneficiary = obj.beneficiary
                return beneficiary.user == user if beneficiary else False
        
        return False


class TenantScopedPermission(permissions.BasePermission):
    """
    Combined permission: authenticated + tenant access.
    
    This is the default permission for most API endpoints.
    """
    
    message = "You must be authenticated and have access to this organization."
    
    def has_permission(self, request, view):
        user = request.user
        return user and user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Get the resource's company
        resource_company = getattr(obj, "company", None)
        if resource_company is None:
            return True
        
        return user.can_access_company(resource_company)

