"""Shared slowapi Limiter — imported by main.py and route modules.

Endpoints opt in via @limiter.limit("N/period"). The middleware wired in
main.py reads app.state.limiter at request time. Keep this module side-
effect-free so importing it doesn't perturb the FastAPI app.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
