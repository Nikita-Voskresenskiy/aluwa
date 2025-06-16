from joserfc import jwt
from env_settings import EnvSettings
from typing import Dict, Any

settings = EnvSettings()
import logging
import hashlib

BOT_TOKEN_HASH = hashlib.sha256(settings.BOT_TOKEN.encode())

def encode_token(payload: Dict):
    return jwt.encode({'alg': 'HS256'}, payload, settings.JWT_SECRET_KEY)
