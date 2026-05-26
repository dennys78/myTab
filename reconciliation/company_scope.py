from django.contrib.auth.models import User
from django.http import JsonResponse

from .models import Company, CompanyMembership

SESSION_KEY = 'active_company_id'


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
    return Company.objects.filter(memberships__user=user).order_by('denominazione', 'id')


def get_active_company(request):
    if not request.user.is_authenticated:
        return None
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
    if user_companies(request.user).filter(id=company_id).exists():
        request.session[SESSION_KEY] = company_id
        return True
    return False


def ensure_user_membership(user, company):
    CompanyMembership.objects.get_or_create(user=user, company=company)


def provision_default_membership(user):
    company = Company.objects.order_by('id').first()
    if company:
        ensure_user_membership(user, company)


def create_company_for_user(user, denominazione='', indirizzo='', piva=''):
    company = Company.objects.create(
        denominazione=(denominazione or 'Nuova azienda').strip(),
        indirizzo=(indirizzo or '').strip(),
        piva=(piva or '').strip(),
    )
    ensure_user_membership(user, company)
    return company
