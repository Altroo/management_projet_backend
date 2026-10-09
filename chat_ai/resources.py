"""Adapter inventory grounded in the native models, filters, serializers and views."""
from dataclasses import dataclass
from project import models as pm, serializers as ps, views as pv
from project.filters import ProjectFilter
from devis.models import Quote
from devis.serializers import QuoteSerializer
from devis.views import QuoteDetailView
from devis.filters import QuoteFilter
from depense.models import Expense
from depense.serializers import ExpenseSerializer
from depense.views import ExpenseDetailView
from depense.filters import ExpenseFilter
from revenu.models import Revenue
from revenu.serializers import RevenueSerializer
from revenu.views import RevenueDetailView
from revenu.filters import RevenueFilter
@dataclass(frozen=True)
class Resource:
    model: object
    serializer: object
    view: object
    filterset: object=None
    editable: tuple=()
RESOURCES={
 'project':Resource(pm.Project,ps.ProjectSerializer,pv.ProjectDetailEditDeleteView,ProjectFilter,('nom','description','notes','chef_de_projet','date_debut','date_fin','budget_total','status')),
 'client':Resource(pm.Client,ps.ClientSerializer,pv.ClientDetailView,None,('nom','telephone','email','ville','adresse')),
 'supplier':Resource(pm.Supplier,ps.SupplierSerializer,pv.SupplierDetailView,None,('nom','contact','specialite')),
 'quote':Resource(Quote,QuoteSerializer,QuoteDetailView,QuoteFilter,('description','number','date','amount_ht','amount_tva','status')),
 'expense':Resource(Expense,ExpenseSerializer,ExpenseDetailView,ExpenseFilter,('description','notes','element','date','montant')),
 'revenue':Resource(Revenue,RevenueSerializer,RevenueDetailView,RevenueFilter,('description','notes','date','montant')),
 'payment_schedule':Resource(pm.ProjectPaymentSchedule,ps.ProjectPaymentScheduleSerializer,pv.ProjectPaymentScheduleDetailView,None,('description','notes','due_date','expected_amount')),
 'budget_entry':Resource(pm.ProjectRealBudgetEntry,ps.ProjectRealBudgetEntrySerializer,pv.ProjectRealBudgetEntryDetailView,None,('stage','description','notes','date','montant_client','montant_fournisseur')),
 'category':Resource(pm.Category,ps.CategorySerializer,None),
 'subcategory':Resource(pm.SubCategory,ps.SubCategorySerializer,None),
}
