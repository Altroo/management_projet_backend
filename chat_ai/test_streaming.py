"""Real JWT, database, ASGI streaming and worker cancellation on isolated fixtures."""
import asyncio,json,threading,uuid
from datetime import timedelta
from unittest.mock import patch
from asgiref.sync import sync_to_async
from django.test import AsyncClient,TransactionTestCase,override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from account.models import CustomUser
from .models import Conversation,InferenceLease
from .security import authorization_stamp

@override_settings(CHAT_AI_ASSISTANT_ENABLED=True)
class StreamingSecurityTests(TransactionTestCase):
    def setUp(self):
        self.user=CustomUser.objects.create_user(email='stream@example.test',password='fixture-password',can_view=True)
        self.conversation=Conversation.objects.create(user=self.user,company_id=1,authorization_stamp=authorization_stamp(self.user.pk),expires_at=timezone.now()+timedelta(days=1))
        self.token=str(RefreshToken.for_user(self.user).access_token)
    async def response(self):
        return await AsyncClient().post(f'/api/ai/v1/conversations/{self.conversation.pk}/messages/',data=json.dumps({'text':'Show projects','request_id':str(uuid.uuid4()),'context':{}}),content_type='application/json',headers={'Authorization':'Bearer '+self.token,'Accept':'text/event-stream'})
    async def test_permission_revocation_before_streamed_results(self):
        started=threading.Event();release=threading.Event()
        class Model:
            def choose(self,*args):started.set();release.wait(5);return {'tool':'search_records','arguments':{'resource':'project'}},{}
        with patch('chat_ai.services.get_model',return_value=Model()):
            response=await self.response();self.assertEqual(response.status_code,200)
            iterator=response.__aiter__();first=await anext(iterator);self.assertIn(b'message.started',first)
            self.assertTrue(await asyncio.to_thread(started.wait,3))
            await sync_to_async(CustomUser.objects.filter(pk=self.user.pk).update)(can_view=False);release.set()
            parts=[part async for part in iterator]
        payload=b''.join(parts);self.assertIn(b'PERMISSION_DENIED',payload);self.assertNotIn(b'message.completed',payload);self.assertNotIn(b'items',payload)
    async def test_jwt_expiry_before_private_stream_delivery(self):
        started=threading.Event();release=threading.Event()
        class Model:
            def choose(self,*args):started.set();release.wait(5);return {'tool':'search_records','arguments':{'resource':'project'}},{}
        with patch('chat_ai.services.get_model',return_value=Model()):
            response=await self.response();iterator=response.__aiter__();await anext(iterator);self.assertTrue(await asyncio.to_thread(started.wait,3))
            future=timezone.now()+timedelta(hours=2)
            with patch('chat_ai.views.timezone.now',return_value=future):
                release.set();parts=[part async for part in iterator]
        payload=b''.join(parts);self.assertIn(b'NOT_AUTHENTICATED',payload);self.assertNotIn(b'message.completed',payload)
    async def test_disconnect_cancels_worker_and_releases_lease(self):
        started=threading.Event();cancelled=threading.Event()
        class Model:
            def choose(self,messages,tools,cancel=None):
                started.set()
                if cancel.wait(5):cancelled.set()
                return {'tool':'search_records','arguments':{'resource':'project'}},{}
        with patch('chat_ai.services.get_model',return_value=Model()):
            response=await self.response();raw=response._iterator;await anext(raw);self.assertTrue(await asyncio.to_thread(started.wait,3))
            await raw.aclose();self.assertTrue(await asyncio.to_thread(cancelled.wait,3))
            for _ in range(100):
                busy=await sync_to_async(InferenceLease.objects.filter(owner__isnull=False).exists)()
                if not busy:break
                await asyncio.sleep(.02)
            self.assertFalse(busy)
