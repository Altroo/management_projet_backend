"""Reuse native user flags and the application's single-company workspace."""
import hashlib
import re
from django.conf import settings
from account.models import CustomUser
from core.permissions import can_view, can_print, can_create, can_update, can_delete
from chat_ai_assistant.contracts import ChatAIError

SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:Bearer\s+)[A-Za-z0-9._-]{16,}|(?:password|api[_-]?key|secret|access[_-]?token)\s*[:=]\s*\S+", re.I)

def validate_text(text):
    if not isinstance(text,str) or not text.strip() or len(text)>4000 or '\x00' in text:
        raise ChatAIError('INVALID_ARGUMENTS')
    if SECRET.search(text): raise ChatAIError('SENSITIVE_INPUT')
    return text.strip()

def authorize(user_id, company_id=1):
    if not settings.CHAT_AI_ASSISTANT_ENABLED: raise ChatAIError('APPLICATION_UNAVAILABLE')
    if type(company_id) is not int or company_id != 1: raise ChatAIError('PERMISSION_DENIED')
    user=CustomUser.objects.filter(pk=user_id,is_active=True).first()
    if user is None: raise ChatAIError('NOT_AUTHENTICATED')
    if not can_view(user): raise ChatAIError('PERMISSION_DENIED')
    return user

def capabilities(user):
    return {name for name,check in [('read',can_view),('print',can_print),('create',can_create),('update',can_update),('delete',can_delete)] if check(user)}

def authorization_stamp(user_id, company_id=1):
    user=authorize(user_id,company_id)
    return hashlib.sha256(repr(('management_projet',user.pk,company_id,user.is_staff,user.is_superuser,sorted(capabilities(user)))).encode()).hexdigest()
