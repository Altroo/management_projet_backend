from datetime import timedelta
from django.test import SimpleTestCase
from django.utils import timezone
from .targets import trusted_target


class OrdinalTargetTests(SimpleTestCase):
    def test_ordinal_precedes_current_page_and_saved_membership(self):
        now = timezone.now()
        resource, noun = ('project', 'project')
        state = {"resource": resource, "ids": [311, 8092, 1456],
                 "expires_at": (now + timedelta(minutes=5)).isoformat()}
        kwargs = dict(instruction=f"Update the third {noun}.", state=state,
                      context={"resource":resource,"identifier":311}, now=now)
        self.assertFalse(trusted_target(resource,311,**kwargs))
        self.assertTrue(trusted_target(resource,1456,**kwargs))
        for expired in [{}, {**state,"expires_at":now.isoformat()}]:
            self.assertFalse(trusted_target(resource,311,**{**kwargs,"state":expired}))

    def test_quote_does_not_override_explicit_native_id(self):
        resource,noun = ('project', 'project')
        self.assertTrue(trusted_target(resource,311,instruction=f'Update {noun} ID 311: name "The third {noun}".',
                                       state={},context={},now=timezone.now()))

    def test_explicit_target_precedes_unrelated_current_and_saved_record(self):
        now=timezone.now()
        kwargs=dict(instruction="Delete client ID 72.",now=now,
                    context={"resource":"project","identifier":311},
                    state={"resource":"project","ids":[311],"expires_at":(now+timedelta(minutes=5)).isoformat()})
        self.assertFalse(trusted_target("project",311,**kwargs))
        self.assertTrue(trusted_target("client",72,**kwargs))

    def test_replacement_text_does_not_authorize_another_record(self):
        now=timezone.now()
        for instruction in ['Update project ID 311 notes to "client ID 72 is the reference".',
                            'Update project ID 311 notes to client ID 72.',
                            'Update project ID 311: description client ID 72.',
                            'Update project ID 311 name: client ID 72.']:
            kwargs=dict(instruction=instruction,now=now,state={},
                        context={"resource":"client","identifier":72})
            with self.subTest(instruction=instruction):
                self.assertTrue(trusted_target("project",311,**kwargs))
                self.assertFalse(trusted_target("client",72,**kwargs))

    def test_explicit_target_cannot_bypass_invalid_ordinal(self):
        now=timezone.now()
        kwargs=dict(instruction="Delete the third project, project ID 311.",now=now,
                    context={"resource":"project","identifier":311},
                    state={"resource":"project","ids":[311,8092,1456],"expires_at":(now+timedelta(minutes=5)).isoformat()})
        self.assertFalse(trusted_target("project",311,**kwargs))
        self.assertFalse(trusted_target("project",1456,**kwargs))
