"""Optional modules/actions: descriptions accepted; a bare slash action explains usage."""
import re
from chat_ai_assistant.clarifications import message_language
from chat_ai_assistant.routing import normalized
from chat_ai_assistant.contracts import ChatAIError
from .security import capabilities
MODULES=[('/projets','project','Projets','Projects'),('/clients','client','Clients','Customers'),('/fournisseurs','supplier','Fournisseurs','Suppliers'),('/devis','quote','Devis','Quotes'),('/depenses','expense','Dépenses','Expenses'),('/revenus','revenue','Revenus','Receipts'),('/echeances','payment_schedule','Échéances','Payment schedules'),('/budgets','budget_entry','Budget réel','Actual budgets'),('/categories','category','Catégories','Categories')]
ALIASES={'/projects':'/projets','/customers':'/clients','/suppliers':'/fournisseurs','/quotes':'/devis','/expenses':'/depenses','/receipts':'/revenus','/schedules':'/echeances','/search':'/voir','/chercher':'/voir','/edit':'/modifier','/delete':'/supprimer','/summary':'/bilan','/help':'/aide'}
def shortcut_catalog(user,language='fr'):
    en=language=='en';caps=capabilities(user)
    items=[{'command':c,'title':english if en else french,'help':'Search this module by a description, project or customer.' if en else 'Recherchez dans ce module par description, projet ou client.','example':c+' '+('project Atlas' if en else 'projet Atlas')} for c,_,french,english in MODULES]
    actions=[('/voir','Rechercher un document','Find a record','/voir '+('quote for project Atlas' if en else 'devis du projet Atlas'),'read'),('/bilan','Synthèse financière','Financial summary','/bilan '+('expenses this month' if en else 'dépenses de ce mois'),'read'),('/modifier','Modifier après confirmation','Edit with confirmation','/modifier '+('description of project Atlas' if en else 'description du projet Atlas'),'update'),('/supprimer','Supprimer après confirmation','Delete with confirmation','/supprimer '+('quote DEV-DEMO' if en else 'devis DEV-DEMO'),'delete'),('/pdf','Rapport PDF d’un projet','Project PDF report','/pdf '+('project Atlas' if en else 'projet Atlas'),'print'),('/aide','Aide des raccourcis','Shortcut help','/aide','read')]
    for c,fr,english,example,cap in actions:
        if cap in caps:items.append({'command':c,'title':english if en else fr,'help':'Describe the record; no internal identifier is needed.' if en else 'Décrivez le document recherché, sans avoir à connaître son identifiant.','example':example})
    return items if 'read' in caps else []
def suggestions(user,language='fr'):
    en=language=='en'
    items=['Show projects in progress.','Show the latest quotes.','Show the latest expenses.','How much did we receive this month?'] if en else ['Affiche les projets en cours.','Montre les derniers devis.','Montre les dernières dépenses.','Combien avons-nous encaissé ce mois ?']
    items.append(('How do I create a project?' if en else 'Comment créer un projet ?') if 'create' in capabilities(user) else ('How do I find a project?' if en else 'Comment retrouver un projet ?'))
    return items

def shortcut_action(text,executor=None,interface_language='fr'):
    if not text.startswith('/'):return None
    parts=text.split(maxsplit=1);command=ALIASES.get(parts[0].casefold(),parts[0].casefold());arg=parts[1].strip() if len(parts)>1 else ''
    language=message_language(text,interface_language);en=language=='en'
    catalog=shortcut_catalog(executor.authorize(),language);item=next((x for x in catalog if x['command']==command),None)
    if not item:
        if command in ('/modifier','/supprimer','/pdf'):raise ChatAIError('PERMISSION_DENIED')
        return {'tool':'clarify','message':'Unknown command. Send /help.' if en else 'Commande inconnue. Envoyez /aide.'}
    if command=='/aide':return {'tool':'clarify','message':('\n'.join(x['command']+' : '+x['title'] for x in catalog))}
    module=next((x for x in MODULES if x[0]==command),None)
    if module and not arg:return {'tool':'search_records','arguments':{'resource':module[1]},'usage_message':item['help']+' '+item['example']}
    if not arg:return {'tool':'clarify','message':item['help']+' '+item['example']}
    return None

def reference_action(text,state):
    if not state.get('ids'):return None
    words=normalized(text).strip().rstrip('.!?')
    values={'first':1,'second':2,'third':3,'premier':1,'premiere':1,'deuxieme':2,'troisieme':3}
    match=re.fullmatch(r'(?:open (?:the )?|ouvre (?:le |la )?)(first|second|third|premier|premiere|deuxieme|troisieme)(?: one| result| resultat)?',words)
    if match:return {'tool':'previous_results','arguments':{'operation':'open','index':values[match[1]]}}
    return None

def knowledge_action(text):
    words=normalized(text).strip()
    if len(text)<300 and not re.search(r'\d|\b(?:then|puis|ensuite|ignore|et|and|current|this|ce|cette)\b',words) and re.match(r'^(?:how (?:do i|to)|comment (?:creer|retrouver|trouver|modifier|supprimer|utiliser)|que signifie|what does)\b',words):return {'tool':'knowledge','arguments':{'query':text}}
    return None


def financial_action(text):
    """Only complete, explicit aggregate sentences; no names/IDs/extra filters ignored."""
    words=normalized(text).strip().rstrip('.!?').strip()
    periods={'this month':'current_month','last month':'previous_month',
             'this year':'current_year','last year':'previous_year','in total':'all_time',
             'ce mois':'current_month','ce mois-ci':'current_month','le mois dernier':'previous_month',
             'cette annee':'current_year',"l'annee derniere":'previous_year','au total':'all_time'}
    match=re.fullmatch(r"how much (?:did|have) we (receive(?:d)?|collect(?:ed)?|spend|spent) (this month|last month|this year|last year|in total)",words)
    if not match:
        match=re.fullmatch(r"combien (?:avons[- ]nous|a[- ]t[- ]on|on a) (encaisse|recu|depense) (ce mois(?:-ci)?|le mois dernier|cette annee|l'annee derniere|au total)",words)
    if not match:return None
    metric='expenses' if match[1] in ('spend','spent','depense') else 'revenue'
    return {'tool':'financial_summary','arguments':{'metric':metric,'period':periods[match[2]]}}

def greeting_action(text):
    """Greeting-only messages never invoke the model or retrieve business records."""
    words=normalized(text).strip().rstrip('.!?').strip()
    words=re.sub(r'\s+',' ',words)
    if words in {'hello','hi','hey','good morning','good afternoon','good evening','hello there'}:
        return {'tool':'clarify','message':'Hello! How can I help you with Management Projet?'}
    if words in {'bonjour','salut','bonsoir','coucou','bonjour a tous'}:
        return {'tool':'clarify','message':'Bonjour ! Comment puis-je vous aider dans Management Projet ?'}
    if words in {'thanks','thank you','thank you very much'}:
        return {'tool':'clarify','message':'You’re welcome!'}
    if words in {'merci','merci beaucoup'}:
        return {'tool':'clarify','message':'Avec plaisir !'}
    return None
