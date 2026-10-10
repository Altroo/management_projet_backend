"""Bounded typed business tools; authorization is trusted Python, never model policy."""
from datetime import date,timedelta
from decimal import Decimal
import time,uuid
from django.conf import settings
from django.db import connection,transaction,OperationalError
from django.db.models import Q,Sum,DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from chat_ai_assistant.contracts import ChatAIError,ChatAITool,ChatAIToolRegistry,object_schema,ID,STRING
from .security import authorize,capabilities,validate_text
from .resources import RESOURCES
from .models import AuditEvent
from .navigation import ChatAINavigationResolver,ROUTES,DETAILS
from .labels import FIELD_LABELS
from .knowledge import ChatAIKnowledgeService
RESOURCE={'type':'string','enum':list(RESOURCES)}
DATE={'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'}
SEARCH=object_schema({'resource':RESOURCE,'query':STRING,'project_name':STRING,'client_name':STRING,'supplier_name':STRING,'status':STRING,'date_from':DATE,'date_to':DATE,'limit':{'type':'integer','minimum':1,'maximum':10},'offset':{'type':'integer','minimum':0,'maximum':100}},['resource'])
METRICS=['revenue','expenses','profit','service_fees','budget','estimates']

def registry():
    specs=[
     ('search_records','Find records by description and combined project/customer/supplier/status/date filters.',SEARCH,('read',)),
     ('get_record','Retrieve a known record or the authorized current-page record.',object_schema({'resource':RESOURCE,'identifier':ID},['resource']),('read',)),
     ('financial_summary','Authoritative native financial metric. Explicit metric required; never guess profit. All-time or local period, optional exact project.',object_schema({'metric':{'type':'string','enum':METRICS},'period':{'type':'string','enum':['all_time','current_month','current_year','previous_month','previous_year','custom']},'project_name':STRING,'project_id':ID,'date_from':DATE,'date_to':DATE},['metric']),('read',)),
     ('navigate','Approved native list, record, edit or new-form route. No arbitrary URL.',object_schema({'resource':{'type':'string','enum':list(ROUTES)+list(DETAILS)+[x+'_edit' for x in DETAILS]+[x+'_new' for x in DETAILS]},'identifier':ID},['resource']),('read',)),
     ('knowledge','Retrieve reviewed permission-aware application procedures and labels.',object_schema({'query':STRING},['query']),('read',)),
     ('previous_results','Resolve only saved results; index is one-based. No context means this tool is unavailable.',object_schema({'operation':{'type':'string','enum':['open','list']},'index':{'type':'integer','minimum':1,'maximum':10}},['operation']),('read',)),
     ('project_report','Offer the native project PDF; print permission required.',object_schema({'identifier':ID},['identifier']),('read','print')),
     ('prepare_change','Propose a known record edit/delete for exact-target confirmation; cannot execute.',object_schema({'resource':{'type':'string','enum':[n for n,r in RESOURCES.items() if r.editable]},'identifier':ID,'operation':{'type':'string','enum':['update','delete']},'changes':{'type':'object','maxProperties':8,'propertyNames':{'enum':sorted({x for r in RESOURCES.values() for x in r.editable})},'additionalProperties':{'type':['string','null'],'maxLength':1000}}},['resource','identifier','operation']),('read',)),
    ]
    return ChatAIToolRegistry([ChatAITool(n,d,s,{'type':'object'},n,application='management_projet',required_capabilities=c,authorization='fresh native flags and single-workspace scope',classification='proposal' if n=='prepare_change' else 'read',audit_classification='business_proposal' if n=='prepare_change' else 'business_read') for n,d,s,c in specs])

class ChatAIToolExecutor:
    def __init__(self,user_id,company_id,request_id,state=None,context=None,audit=True,instruction=None):
        self.user_id,self.company_id,self.request_id=user_id,company_id,request_id
        self.state=state or {};self.context=context or {};self.audit=audit
        # Conversation planning supplies the validated current user instruction.
        # Missing instructions never bypass target validation.
        self.instruction=instruction
    def authorize(self):return authorize(self.user_id,self.company_id)
    authorize_context=authorize
    def capabilities(self):return capabilities(self.authorize())
    def output_labels(self):return FIELD_LABELS
    def authorize_knowledge(self,docs):
        if not ChatAIKnowledgeService.sources_authorized([{'document_id':d['document_id'],'version':d['version']} for d in docs],self.company_id,self.capabilities()):raise ChatAIError('CONTEXT_EXPIRED')
    def execute(self,name,args):
        started=time.monotonic();outcome='denied'
        try:
            user=self.authorize();tool=registry().validate(name,args)
            if not set(tool.required_capabilities)<=self.capabilities():raise ChatAIError('PERMISSION_DENIED')
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:cursor.execute('SET LOCAL statement_timeout = %s',[tool.timeout_seconds*1000])
                    result=getattr(self,name)(**args)
                    if time.monotonic()-started>tool.timeout_seconds:raise ChatAIError('TOOL_TIMEOUT')
                    self.authorize()
            except OperationalError as exc:
                if getattr(exc.__cause__,'pgcode',None) in ('57014','55P03'):raise ChatAIError('TOOL_TIMEOUT') from None
                raise
            outcome='allowed';return result
        finally:
            if self.audit:AuditEvent.objects.create(user_id=self.user_id,actor_id=self.user_id,application='management_projet',company_id=self.company_id,tool=name[:64],outcome=outcome,correlation_id=self.request_id,model_version=settings.CHAT_AI_MODEL_ID,duration_ms=max(0,int((time.monotonic()-started)*1000)))
    def queryset(self,resource):
        self.authorize()
        if resource not in RESOURCES:raise ChatAIError('INVALID_ARGUMENTS')
        return RESOURCES[resource].model.objects.all()
    def record(self,resource,identifier):
        if type(identifier) is not int or not 0<identifier<=2147483647:raise ChatAIError('INVALID_ARGUMENTS')
        obj=self.queryset(resource).filter(pk=identifier).first()
        if obj is None:raise ChatAIError('NOT_FOUND')
        return obj
    def serialize(self,resource,obj):
        # Deliberately bounded output, no native serializer's unbounded related-record history.
        item={'id':obj.pk,'name':str(getattr(obj,'nom',getattr(obj,'name',getattr(obj,'number',getattr(obj,'stage',getattr(obj,'description',''))))))[:300]}
        for field in ('description','notes'):
            value=getattr(obj,field,None)
            if value:item[field]=str(value)[:400]
        if hasattr(obj,'project'):item['project']=obj.project.nom[:300]
        if resource=='project':item['client']=obj.client.nom if obj.client_id else obj.nom_client
        elif hasattr(obj,'project'):item['client']=obj.project.client.nom if obj.project.client_id else obj.project.nom_client
        if getattr(obj,'supplier_id',None):item['supplier']=obj.supplier.nom
        if hasattr(obj,'status'):item['status']=obj.get_status_display() if hasattr(obj,'get_status_display') else obj.status
        value=getattr(obj,'date',getattr(obj,'date_debut',getattr(obj,'due_date',None)))
        if value:item['date']=value.isoformat()
        for field in ('montant','amount_ttc','budget_total','expected_amount'):
            if hasattr(obj,field):item['amount']=str(getattr(obj,field));item['currency']='MAD';break
        if resource=='budget_entry':item['details']=[{'label':'Montant facturé au client','label_en':'Amount invoiced to customer','value':str(obj.montant_client)+' MAD'},{'label':'Montant payé au fournisseur','label_en':'Amount paid to supplier','value':str(obj.montant_fournisseur)+' MAD'}]
        if resource in DETAILS:item['navigation']=ChatAINavigationResolver.resolve(resource,1,obj.pk)
        elif resource in ('payment_schedule','budget_entry'):item['navigation']=ChatAINavigationResolver.resolve('project',1,obj.project_id)
        return item
    def read_records(self,resource,ids):
        if not isinstance(ids,list) or len(ids)>10 or any(type(i) is not int or i<1 for i in ids):raise ChatAIError('INVALID_ARGUMENTS')
        objects={obj.pk:obj for obj in self.queryset(resource).filter(pk__in=ids)}
        return [self.serialize(resource,objects[i]) for i in ids if i in objects]
    def search_records(self,resource,query='',project_name='',client_name='',supplier_name='',status='',date_from=None,date_to=None,limit=10,offset=0):
        qs=self.queryset(resource);spec=RESOURCES[resource];params={}
        if date_from or date_to:
            try:dates=[date.fromisoformat(v) for v in (date_from,date_to) if v]
            except ValueError:raise ChatAIError('INVALID_ARGUMENTS') from None
            if len(dates)==2 and dates[0]>dates[1]:raise ChatAIError('INVALID_ARGUMENTS')
        if spec.filterset:
            if query:params['search']=query
            if status:
                if resource not in ('project','quote'):raise ChatAIError('INVALID_ARGUMENTS')
                choices=dict(spec.model._meta.get_field('status').choices or [])
                if resource=='project':choices=dict(spec.model.STATUS_CHOICES)
                if status not in choices:raise ChatAIError('INVALID_ARGUMENTS')
                params['status']=status
            if date_from:params['date_debut_after' if resource=='project' else 'date_after']=date_from
            if date_to:params['date_debut_before' if resource=='project' else 'date_before']=date_to
            filters=spec.filterset(params,queryset=qs)
            if not filters.is_valid():raise ChatAIError('INVALID_ARGUMENTS')
            qs=filters.qs
        else:
            if status:raise ChatAIError('INVALID_ARGUMENTS')
            if query:
                fields=['nom','contact','specialite'] if resource=='supplier' else ['nom','email','telephone','ville'] if resource=='client' else ['name'] if resource in ('category','subcategory') else ['description','notes']+(['stage'] if resource=='budget_entry' else [])
                match=Q()
                for field in fields:match|=Q(**{field+'__icontains':query})
                qs=qs.filter(match)
            if date_from or date_to:
                if resource not in ('budget_entry','payment_schedule'):raise ChatAIError('INVALID_ARGUMENTS')
                field='due_date' if resource=='payment_schedule' else 'date'
                if date_from:qs=qs.filter(**{field+'__gte':date_from})
                if date_to:qs=qs.filter(**{field+'__lte':date_to})
        if project_name:
            if resource=='project':qs=qs.filter(nom__icontains=project_name)
            elif hasattr(spec.model,'project'):qs=qs.filter(project__nom__icontains=project_name)
            else:raise ChatAIError('INVALID_ARGUMENTS')
        if client_name:
            if resource=='client':qs=qs.filter(nom__icontains=client_name)
            elif resource=='project':qs=qs.filter(Q(client__nom__icontains=client_name)|Q(nom_client__icontains=client_name))
            elif hasattr(spec.model,'project'):qs=qs.filter(Q(project__client__nom__icontains=client_name)|Q(project__nom_client__icontains=client_name))
            else:raise ChatAIError('INVALID_ARGUMENTS')
        if supplier_name:
            if resource=='supplier':qs=qs.filter(nom__icontains=supplier_name)
            elif resource in ('quote','expense'):qs=qs.filter(supplier__nom__icontains=supplier_name)
            else:raise ChatAIError('INVALID_ARGUMENTS')
        # Newest business dates, stable tie-breaker; no private total counts.
        field='date_debut' if resource=='project' else 'due_date' if resource=='payment_schedule' else 'date' if resource in ('quote','expense','revenue','budget_entry') else 'id'
        found=list(qs.order_by('-'+field,'-id').distinct()[offset:offset+limit+1])
        items=[self.serialize(resource,obj) for obj in found[:limit]]
        self.state={'resource':resource,'ids':[x['id'] for x in items],'expires_at':(timezone.now()+timedelta(minutes=20)).isoformat()}
        return {'type':'record_list','resource':resource,'items':items,'has_more':len(found)>limit}
    def get_record(self,resource,identifier=None):
        if identifier is None:
            if self.context.get('resource')!=resource:raise ChatAIError('INVALID_ARGUMENTS')
            identifier=self.context.get('identifier')
        obj=self.record(resource,identifier)
        self.state={'resource':resource,'ids':[obj.pk],'expires_at':(timezone.now()+timedelta(minutes=20)).isoformat()}
        return {'type':'record_list','resource':resource,'items':[self.serialize(resource,obj)]}
    def navigate(self,resource,identifier=None):
        self.authorize()
        if resource.endswith('_new'):
            if 'create' not in self.capabilities():raise ChatAIError('PERMISSION_DENIED')
        elif resource.endswith('_edit'):
            if 'update' not in self.capabilities():raise ChatAIError('PERMISSION_DENIED')
            self.record(resource[:-5],identifier)
        elif resource in DETAILS:self.record(resource,identifier)
        target=ChatAINavigationResolver.resolve(resource,self.company_id,identifier)
        return {'type':'navigation','target':target}
    def previous_results(self,operation,index=None):
        if not self.state.get('ids') or self.state.get('expires_at','')<timezone.now().isoformat():raise ChatAIError('CONTEXT_EXPIRED')
        resource=self.state['resource'];items=self.read_records(resource,self.state['ids'])
        if len(items)!=len(self.state['ids']):raise ChatAIError('CONTEXT_EXPIRED')
        if operation=='list':return {'type':'record_list','resource':resource,'items':items}
        if index is None or index>len(items):raise ChatAIError('INVALID_ARGUMENTS')
        target=items[index-1].get('navigation')
        if not target:raise ChatAIError('INVALID_ARGUMENTS')
        return {'type':'navigation','target':target}
    def knowledge(self,query):
        self.authorize();return {'type':'knowledge','documents':ChatAIKnowledgeService().retrieve(query,1,self.capabilities())}
    def project_report(self,identifier):
        if 'print' not in self.capabilities():raise ChatAIError('PERMISSION_DENIED')
        obj=self.record('project',identifier)
        return {'type':'pdf','resource':'project','record_id':obj.pk,'number':obj.nom}
    def prepare_change(self,resource,identifier,operation,changes=None):
        from .actions import prepare
        return prepare(self,resource,identifier,operation,changes or {})
    def financial_summary(self,metric,period='all_time',project_name='',project_id=None,date_from=None,date_to=None):
        self.authorize()
        from project.models import Project
        from project.views import _project_dashboard_payload,_multi_project_dashboard_payload,_expense_total,_service_fee_total
        from devis.services import project_estimate_summary
        from revenu.models import Revenue
        from depense.models import Expense
        today=timezone.localdate();start=end=None
        if project_name:
            matches=list(Project.objects.filter(Q(nom__iexact=project_name)|Q(nom__icontains=project_name))[:2])
            if not matches:raise ChatAIError('NOT_FOUND')
            if len(matches)>1:raise ChatAIError('MULTIPLE_MATCHES')
            if project_id is not None and project_id!=matches[0].pk:raise ChatAIError('INVALID_ARGUMENTS')
            project_id=matches[0].pk
        project=self.record('project',project_id) if project_id is not None else None
        if period=='custom':
            try:start,end=date.fromisoformat(date_from),date.fromisoformat(date_to)
            except (ValueError,TypeError):raise ChatAIError('INVALID_ARGUMENTS') from None
            if start>end:raise ChatAIError('INVALID_ARGUMENTS')
        elif date_from or date_to:raise ChatAIError('INVALID_ARGUMENTS')
        elif period=='current_month':start=today.replace(day=1);end=today
        elif period=='current_year':start=today.replace(month=1,day=1);end=today
        elif period=='previous_month':end=today.replace(day=1)-timedelta(days=1);start=end.replace(day=1)
        elif period=='previous_year':start=date(today.year-1,1,1);end=date(today.year-1,12,31)
        if metric in ('budget','estimates') and period!='all_time':raise ChatAIError('INVALID_ARGUMENTS')
        if metric=='estimates':
            if project is None:raise ChatAIError('INVALID_ARGUMENTS')
            value=project_estimate_summary(project)['estimated']
        elif start is None:
            data=_project_dashboard_payload(project) if project else _multi_project_dashboard_payload()
            keys={'revenue':'revenue_total','expenses':'depenses_totales','profit':'benefice','service_fees':'service_fees','budget':'budget_total'} if project else {'revenue':'total_revenue','expenses':'total_expenses','profit':'total_profit','service_fees':'total_service_fees','budget':'total_budget'}
            value=data[keys[metric]]
        else:
            revenues=Revenue.objects.filter(date__range=(start,end));expenses=Expense.objects.filter(date__range=(start,end))
            if project:revenues=revenues.filter(project=project);expenses=expenses.filter(project=project)
            received=revenues.aggregate(total=Coalesce(Sum('montant'),0,output_field=DecimalField()))['total'];spent=_expense_total(expenses,include_service_fees=False)
            value={'revenue':received,'expenses':spent,'profit':received-spent,'service_fees':_service_fee_total(expenses)}[metric]
        result={'type':'financial_summary','metric':metric,'value':str(value),'currency':'MAD','basis':'native_dashboard','scope':project.nom if project else 'all_projects'}
        if start:result['period']={'from':start.isoformat(),'to':end.isoformat()}
        return result
