"""Proposals from the planner require a target supplied by trusted request state."""
from datetime import datetime
import re
import unicodedata

ALIASES = {
    'project': r'projet|project', 'client': r'client|customer',
    'supplier': r'fournisseur|supplier', 'quote': r'devis|quote|estimate',
    'expense': r'depense|expense', 'revenue': r'revenu|recette|encaissement|revenue|receipt',
    'payment_schedule': r'echeance|payment schedule',
    'budget_entry': r'ligne de budget|budget entry',
}


def trusted_target(resource, identifier, *, instruction, context, state, now):
    if type(identifier) is not int or identifier < 1 or not isinstance(instruction, str):
        return False
    if context.get('resource') == resource and type(context.get('identifier')) is int and context['identifier'] == identifier:
        return True
    ids = state.get('ids', [])
    expiry = state.get('expires_at')
    if state.get('resource') == resource and isinstance(ids, list) and any(type(value) is int and value == identifier for value in ids) and isinstance(expiry, str):
        try:
            expires_at = datetime.fromisoformat(expiry)
            if expires_at.utcoffset() is not None and expires_at > now:
                return True
        except (TypeError, ValueError):
            pass
    aliases = ALIASES.get(resource)
    if not aliases:
        return False
    words = ''.join(char for char in unicodedata.normalize('NFKD', instruction.casefold()) if not unicodedata.combining(char))
    # Quotes have a separate business number; bare numbers must be searched.
    marker = r'(?:id|identifiant)\s*[:#]?\s*'
    if resource != 'quote':
        marker = r'(?:' + marker + r'|(?:numero|number|no\.|n[°o])\s*[:#]?\s*|#\s*)?'
    # A complete ID token excludes leading-zero, decimal and compound references.
    pattern = r'\b(?:' + aliases + r')(?:s)?\s+' + marker + r'([1-9][0-9]*)(?=$|\s|[.!?;,:](?:\s|$))'
    return any(int(match.group(1)) == identifier for match in re.finditer(pattern, words))
