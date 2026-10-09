FIELD_LABELS = {'nom':'Nom','description':'Description','notes':'Notes','numero_telephone':'Téléphone','adresse':'Adresse','email':'E-mail','ville':'Ville','status':'Statut','budget_total':'Budget total','montant':'Montant','amount_ht':'Montant HT','amount_tva':'TVA','amount_ttc':'Montant TTC','chef_de_projet':'Chef de projet','date_debut':'Date de début','date_fin':'Date de fin'}
RESOURCE_LABELS={'project':'Projet','client':'Client','supplier':'Fournisseur','quote':'Devis','expense':'Dépense','revenue':'Revenu','payment_schedule':'Échéance','budget_entry':'Budget réel','category':'Catégorie','subcategory':'Sous-catégorie'}
def selected_action_text(operation,resource):
    return ('Supprimer' if operation=='delete' else 'Modifier')+' · '+RESOURCE_LABELS.get(resource,'Document')

FIELD_LABELS.update({"telephone":"Téléphone","number":"Numéro de devis","date":"Date","due_date":"Date prévue","expected_amount":"Montant prévu","stage":"Étape du projet","montant_client":"Montant facturé au client","montant_fournisseur":"Montant payé au fournisseur","element":"Élément de dépenses"})

FIELD_LABELS.update({"contact":"Contact","specialite":"Spécialité"})
