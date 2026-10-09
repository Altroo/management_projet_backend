"""Approved native routes; no model-generated URL is accepted."""
from chat_ai_assistant.contracts import ChatAIError
ROUTES={'projects':'projects','clients':'clients','suppliers':'suppliers','quotes':'quotes','expenses':'expenses','revenues':'revenues','dashboard':''}
DETAILS={'project':'projects','client':'clients','supplier':'suppliers','quote':'quotes','expense':'expenses','revenue':'revenues'}
class ChatAINavigationResolver:
    @staticmethod
    def resolve(resource,company_id,identifier=None):
        if company_id!=1: raise ChatAIError('PERMISSION_DENIED')
        action=''
        base=resource
        if resource.endswith('_edit'): base=resource[:-5];action='/edit'
        if resource.endswith('_new'):
            base=resource[:-4]
            if base not in DETAILS or identifier is not None: raise ChatAIError('INVALID_ARGUMENTS')
            path='/dashboard/'+DETAILS[base]+'/new'
        elif base in DETAILS and type(identifier) is int and 0<identifier<=2147483647:
            path='/dashboard/'+DETAILS[base]+'/'+str(identifier)+action
        elif resource in ROUTES and identifier is None:
            path='/dashboard/'+ROUTES[resource]
        else: raise ChatAIError('INVALID_ARGUMENTS')
        return {'application':'management_projet','resource':resource,'identifier':identifier,'company_id':1,'path':path}
