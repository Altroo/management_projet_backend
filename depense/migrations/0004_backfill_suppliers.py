from django.db import migrations


def backfill_suppliers(apps, schema_editor):
    Expense = apps.get_model("depense", "Expense")
    Supplier = apps.get_model("project", "Supplier")

    expenses = Expense.objects.exclude(fournisseur__isnull=True).exclude(fournisseur="")
    for expense in expenses.iterator():
        supplier_name = (expense.fournisseur or "").strip()
        if not supplier_name:
            continue

        supplier, _ = Supplier.objects.get_or_create(nom=supplier_name)
        if expense.supplier_id is None:
            expense.supplier_id = supplier.id
            expense.save(update_fields=["supplier"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("depense", "0003_expense_supplier_historicalexpense_supplier_and_more"),
        ("project", "0003_seed_statuses_and_clients"),
    ]

    operations = [
        migrations.RunPython(backfill_suppliers, noop_reverse),
    ]
