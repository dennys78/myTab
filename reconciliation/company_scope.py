from django.contrib.auth.models import User
from django.http import JsonResponse

from .models import Company, CompanyMembership

SESSION_KEY = 'active_company_id'


def is_admin_user(user):
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def serialize_company(company):
    if not company:
        return None
    return {
        'id': company.id,
        'denominazione': company.denominazione,
        'indirizzo': company.indirizzo,
        'piva': company.piva,
    }


def user_companies(user):
    if not user.is_authenticated:
        return Company.objects.none()
    if is_admin_user(user):
        return Company.objects.all().order_by('denominazione', 'id')
    return Company.objects.filter(memberships__user=user).order_by('denominazione', 'id')


def get_user_assigned_company(user):
    if not user.is_authenticated or is_admin_user(user):
        return None
    membership = user.company_memberships.select_related('company').first()
    return membership.company if membership else None


def get_active_company(request):
    if not request.user.is_authenticated:
        return None

    if not is_admin_user(request.user):
        company = get_user_assigned_company(request.user)
        if company:
            request.session[SESSION_KEY] = company.id
        return company

    company_id = request.session.get(SESSION_KEY)
    qs = user_companies(request.user)
    if company_id:
        company = qs.filter(id=company_id).first()
        if company:
            return company
    company = qs.first()
    if company:
        request.session[SESSION_KEY] = company.id
    return company


def bind_company(request):
    company = get_active_company(request)
    if not company:
        return None, JsonResponse(
            {'status': 'error', 'error': 'Nessuna azienda associata al tuo account.'},
            status=403,
        )
    return company, None


def set_active_company(request, company_id):
    if not is_admin_user(request.user):
        return False
    if user_companies(request.user).filter(id=company_id).exists():
        request.session[SESSION_KEY] = company_id
        return True
    return False


def ensure_user_membership(user, company):
    CompanyMembership.objects.get_or_create(user=user, company=company)


def set_user_company(user, company):
    CompanyMembership.objects.filter(user=user).delete()
    if company:
        CompanyMembership.objects.create(user=user, company=company)


def provision_default_membership(user):
    company = Company.objects.order_by('id').first()
    if company:
        set_user_company(user, company)


def create_company_for_user(user, denominazione='', indirizzo='', piva=''):
    company = Company.objects.create(
        denominazione=(denominazione or 'Nuova azienda').strip(),
        indirizzo=(indirizzo or '').strip(),
        piva=(piva or '').strip(),
    )
    ensure_user_membership(user, company)
    return company
