from django.shortcuts import redirect
from django.contrib import messages
from .models import CompanyMembership

def company_admin_required(view_func):
    def wrapper_func(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Debes iniciar sesión para acceder a esta página.")
            return redirect('login')

        # Check if a membership exists for the user with an admin role
        if CompanyMembership.objects.filter(user=request.user, role='admin').exists():
            return view_func(request, *args, **kwargs)
        
        # Handle cases where the user is a member but not an admin, or has no membership
        if CompanyMembership.objects.filter(user=request.user).exists():
            messages.error(request, "No tienes permisos de administrador para realizar esta acción.")
            return redirect('company_index')
        else:
            messages.error(request, "No tienes una empresa asociada.")
            return redirect('user_index')
    return wrapper_func

def company_member_required(view_func):
    def wrapper_func(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Debes iniciar sesión para acceder a esta página.")
            return redirect('login')

        # Check if the user is a member of any company
        if CompanyMembership.objects.filter(user=request.user).exists():
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "No perteneces a ninguna empresa para acceder a esta página.")
            return redirect('user_index')
    return wrapper_func
