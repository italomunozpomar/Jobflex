from .models import CompanyMembership

def company_context(request):
    company_instance = None
    if request.user.is_authenticated:
        try:
            user_company_membership = CompanyMembership.objects.filter(user=request.user).first()
            if user_company_membership:
                company_instance = user_company_membership.company
        except CompanyMembership.DoesNotExist:
            pass
    return {'company': company_instance}
