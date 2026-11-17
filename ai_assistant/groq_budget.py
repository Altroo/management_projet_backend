"""One atomic quota budget shared by all applications using the Groq gateway."""

import hashlib
import math
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import caches
from rest_framework.exceptions import Throttled

from .exceptions import ModelUnavailable

RESERVE = """
local blocked=tonumber(redis.call('GET',KEYS[3]) or '0')
if blocked>tonumber(ARGV[1]) then return math.ceil(blocked-tonumber(ARGV[1])) end
local rpm=tonumber(redis.call('HGET',KEYS[1],'requests') or '0')
local tpm=tonumber(redis.call('HGET',KEYS[1],'tokens') or '0')
local rpd=tonumber(redis.call('HGET',KEYS[2],'requests') or '0')
local tpd=tonumber(redis.call('HGET',KEYS[2],'tokens') or '0')
if rpd+1>tonumber(ARGV[5]) or tpd+tonumber(ARGV[8])>tonumber(ARGV[7]) then return math.ceil(tonumber(ARGV[3])-tonumber(ARGV[1])) end
if rpm+1>tonumber(ARGV[4]) or tpm+tonumber(ARGV[8])>tonumber(ARGV[6]) then return math.ceil(tonumber(ARGV[2])-tonumber(ARGV[1])) end
redis.call('HINCRBY',KEYS[1],'requests',1)
redis.call('HINCRBY',KEYS[1],'tokens',ARGV[8])
redis.call('HINCRBY',KEYS[2],'requests',1)
redis.call('HINCRBY',KEYS[2],'tokens',ARGV[8])
redis.call('EXPIREAT',KEYS[1],tonumber(ARGV[2])+60)
redis.call('EXPIREAT',KEYS[2],tonumber(ARGV[3])+60)
return 0
"""
SETTLE = """
for i=1,2 do
 if redis.call('EXISTS',KEYS[i])==1 then
  local value=redis.call('HINCRBY',KEYS[i],'tokens',ARGV[1])
  if value<0 then redis.call('HSET',KEYS[i],'tokens',0) end
 end
end
return 1
"""
BLOCK = """
local old=tonumber(redis.call('GET',KEYS[1]) or '0')
if tonumber(ARGV[1])>old then redis.call('SET',KEYS[1],ARGV[1],'EX',ARGV[2]) end
return 1
"""


class GroqQuotaDeferred(Throttled):
    default_detail = (
        "L’assistant a atteint sa limite temporaire. Veuillez réessayer plus tard."
    )
    default_code = "ai_rate_limited"


@dataclass
class Reservation:
    minute_key: str
    day_key: str
    tokens: int
    settled: bool = False


class GroqBudget:
    def __init__(self, client=None, clock=time.time):
        self.clock = clock
        if client is None:
            cache = caches["ai_assistant"]
            backend = getattr(cache, "_cache", None)
            if not hasattr(backend, "get_client"):
                raise ModelUnavailable()
            client = backend.get_client(write=True)
        self.client = client
        digest = hashlib.sha256(
            (settings.GROQ_API_KEY + "\0" + settings.GROQ_MODEL).encode()
        ).hexdigest()[:24]
        self.prefix = "groq-budget:" + digest

    def reserve(self, tokens, background=False):
        if tokens > settings.GROQ_TPM:
            raise ValueError("Groq request exceeds the configured minute budget")
        now = self.clock()
        minute_end = (int(now) // 60 + 1) * 60
        day_end = (int(now) // 86400 + 1) * 86400
        keys = (
            self.prefix + ":m:" + str(int(now) // 60),
            self.prefix + ":d:" + str(int(now) // 86400),
            self.prefix + ":blocked",
        )
        fraction = settings.GROQ_BACKGROUND_SHARE if background else 1
        try:
            wait = self.client.eval(
                RESERVE,
                3,
                *keys,
                now,
                minute_end,
                day_end,
                settings.GROQ_RPM,
                max(1, int(settings.GROQ_RPD * fraction)),
                settings.GROQ_TPM,
                max(1, int(settings.GROQ_TPD * fraction)),
                tokens
            )
        except Exception as exc:
            raise ModelUnavailable() from exc
        if wait:
            raise GroqQuotaDeferred(wait=max(1, int(wait)))
        return Reservation(keys[0], keys[1], tokens)

    def settle(self, reservation, actual_tokens):
        if reservation.settled:
            return
        reservation.settled = True
        if not isinstance(actual_tokens, int) or actual_tokens < 0:
            return
        try:
            self.client.eval(
                SETTLE,
                2,
                reservation.minute_key,
                reservation.day_key,
                actual_tokens - reservation.tokens,
            )
        except Exception:
            # An unreleased reservation is conservative; it cannot exceed quotas.
            pass

    def block(self, wait):
        wait = max(1, math.ceil(wait))
        try:
            self.client.eval(
                BLOCK, 1, self.prefix + ":blocked", self.clock() + wait, wait + 1
            )
        except Exception:
            pass
