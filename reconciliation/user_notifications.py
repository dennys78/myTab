"""Preferenze notifiche per utente (push browser + Telegram)."""

from __future__ import annotations

import json

from django.contrib.auth.models import User

from .company_scope import get_user_assigned_company, is_admin_user, user_companies
from .models import AcquisitionDraft, AppSetting, UserProfile


def user_receives_notifications(user) -> bool:
    if not user or not user.is_active:
        return False
    try:
        return bool(user.profile.receive_notifications)
    except UserProfile.DoesNotExist:
        return True


def set_user_receive_notifications(user, enabled: bool) -> bool:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.receive_notifications = bool(enabled)
    profile.save(update_fields=['receive_notifications'])
    return profile.receive_notifications


def filter_users_with_notifications(users):
    return [user for user in users if user_receives_notifications(user)]


def company_users_for_company(company):
    """Utenti attivi con accesso all'azienda (base per push e Telegram)."""
    if not company:
        return []
    eligible = []
    for user in User.objects.filter(is_active=True).select_related('profile'):
        if is_admin_user(user):
            if user_companies(user).filter(id=company.id).exists():
                eligible.append(user)
        else:
            assigned = get_user_assigned_company(user)
            if assigned and assigned.id == company.id:
                eligible.append(user)
    return eligible


def company_users_with_notifications(company):
    return filter_users_with_notifications(company_users_for_company(company))


def user_belongs_to_company(user, company) -> bool:
    if not user or not company:
        return False
    if is_admin_user(user):
        return user_companies(user).filter(id=company.id).exists()
    assigned = get_user_assigned_company(user)
    return bool(assigned and assigned.id == company.id)


def link_telegram_chat_to_user(company, chat_id, telegram_username) -> None:
    """Associa chat Telegram a un operatore myTab (username uguale a Telegram)."""
    username = str(telegram_username or '').strip()
    if not username or not chat_id or not company:
        return
    user = User.objects.filter(username__iexact=username, is_active=True).first()
    if not user or not user_belongs_to_company(user, company):
        return
    profile, _ = UserProfile.objects.get_or_create(user=user)
    chat_id = str(chat_id).strip()
    if profile.telegram_chat_id != chat_id:
        profile.telegram_chat_id = chat_id
        profile.save(update_fields=['telegram_chat_id'])


def telegram_chat_ids_for_company(company):
    """Chat Telegram degli operatori con notifiche abilitate."""
    if not company:
        return []

    eligible_users = company_users_with_notifications(company)
    eligible_ids = {user.id for user in eligible_users}
    eligible_usernames = {user.username for user in eligible_users}
    eligible_usernames_lower = {name.lower() for name in eligible_usernames}
    chat_ids: set[str] = set()

    if eligible_ids:
        chat_ids.update(
            UserProfile.objects.filter(user_id__in=eligible_ids)
            .exclude(telegram_chat_id='')
            .values_list('telegram_chat_id', flat=True)
        )

    draft_pairs = (
        AcquisitionDraft.objects.filter(company=company)
        .exclude(telegram_chat_id='')
        .values_list('telegram_chat_id', 'operator')
        .distinct()
    )
    for chat_id, operator in draft_pairs:
        op = str(operator or '').strip()
        if op in eligible_usernames or op.lower() in eligible_usernames_lower:
            chat_ids.add(str(chat_id).strip())

    try:
        raw = AppSetting.objects.get(company=company, key='telegram_chat_ids').value
        legacy_ids = [str(chat_id).strip() for chat_id in json.loads(raw)]
    except (AppSetting.DoesNotExist, json.JSONDecodeError, TypeError):
        legacy_ids = []

    if eligible_usernames and legacy_ids:
        for chat_id in legacy_ids:
            if not chat_id or chat_id in chat_ids:
                continue
            if AcquisitionDraft.objects.filter(
                company=company,
                telegram_chat_id=chat_id,
                operator__in=list(eligible_usernames),
            ).exists():
                chat_ids.add(chat_id)

    return sorted(chat_id for chat_id in chat_ids if chat_id)
