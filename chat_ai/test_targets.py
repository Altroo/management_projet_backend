import unittest
from datetime import datetime, timedelta, timezone
from .targets import trusted_target
NOW=datetime(2030,1,1,tzinfo=timezone.utc)

class TargetTests(unittest.TestCase):
    def check(self,instruction='',context=None,state=None,resource='quote',identifier=17):
        return trusted_target(resource,identifier,instruction=instruction,context=context or {},state=state or {},now=NOW)
    def test_descriptive_request_cannot_validate_a_guessed_id(self):
        self.assertFalse(self.check('Delete the painting quote from the named supplier.'))
    def test_unrelated_dates_and_document_numbers_are_not_internal_ids(self):
        for text in ['Delete the quote for October 2030.','Supprime le devis du client pour octobre 2030.','Delete quote DEV-17.']:
            with self.subTest(text=text):self.assertFalse(self.check(text))
    def test_explicit_bilingual_resource_id(self):
        for text in ['Delete quote ID 17.','Supprime le devis identifiant 17.','Update quote id: 17.']:
            with self.subTest(text=text):self.assertTrue(self.check(text))
        self.assertFalse(self.check('Delete client 17.'))
        self.assertTrue(self.check('Update client ID 12: City Fès.',resource='client',identifier=12))
        self.assertTrue(self.check('Update quote ID 12: description test.',identifier=12))
        for text in ['Modifie le client numéro 12 : Ville Fès.', 'Update customer number 12: City Fès.', 'Update client no. 12.', 'Modifie le client n°12.']:
            with self.subTest(text=text):self.assertTrue(self.check(text,resource='client',identifier=12))
        for text in ['Delete quote number 12.', 'Supprime le devis numéro 12.']:
            with self.subTest(text=text):self.assertFalse(self.check(text,identifier=12))
    def test_compound_numeric_references_cannot_approve_internal_ids(self):
        for text,identifier in [('Supprime le devis 0783/26.',783),('Delete quote 12-2026.',12),('Delete quote number 12.50.',12),('Delete quote ID 12-2026.',12),('Delete quote ID 12.50.',12),('Delete quote ID 0017.',17),('Delete quote 17.',17)]:
            with self.subTest(text=text):self.assertFalse(self.check(text,identifier=identifier))
        self.assertTrue(self.check('Update client 17.',resource='client'))
    def test_current_target_requires_matching_resource_and_id(self):
        self.assertTrue(self.check('Delete this quote.',context={'resource':'quote','identifier':17}))
        self.assertFalse(self.check(context={'resource':'client','identifier':17}))
        self.assertFalse(self.check(context={'resource':'quote','identifier':18}))
    def test_results_require_membership_resource_and_freshness(self):
        state={'resource':'quote','ids':[17],'expires_at':(NOW+timedelta(minutes=1)).isoformat()}
        self.assertTrue(self.check(state=state))
        for bad in [{**state,'ids':[18]},{**state,'resource':'client'},{**state,'expires_at':NOW.isoformat()},{**state,'expires_at':'bad'},{**state,'expires_at':'2030-01-02T00:00:00'}]:
            with self.subTest(state=bad):self.assertFalse(self.check(state=bad))
    def test_boolean_ids_are_rejected(self):
        self.assertFalse(self.check('Delete quote 1.',identifier=True))
        self.assertFalse(self.check(identifier=1,context={'resource':'quote','identifier':True}))
        self.assertFalse(self.check(identifier=1,state={'resource':'quote','ids':[True],'expires_at':(NOW+timedelta(minutes=1)).isoformat()}))
    def test_missing_instruction_has_no_bypass(self):
        self.assertFalse(self.check())
    def test_aware_offsets_are_compared_as_instants(self):
        self.assertTrue(self.check(state={'resource':'quote','ids':[17],'expires_at':'2030-01-01T01:01:00+01:00'}))
        self.assertFalse(self.check(state={'resource':'quote','ids':[17],'expires_at':'2030-01-01T01:00:00+01:00'}))

if __name__=='__main__':unittest.main()
