"""Rate limiting (slowapi) — по IP-адресу клиента."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
