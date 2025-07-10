from joserfc import jwt
from env_settings import env
from typing import Dict, Any


import logging
import hashlib
import hmac

BOT_TOKEN_HASH = hashlib.sha256(env.BOT_TOKEN.encode())

def encode_token(payload: Dict):
    return jwt.encode({'alg': 'HS256'}, payload, env.JWT_SECRET_KEY)

def encode_query_data(params: dict) -> dict:
    """
    Encode query parameters for Telegram bot in the correct format.

    Args:
        params: Dictionary of parameters to encode
        bot_token: Your Telegram bot token (used to compute the hash)

    Returns:
        Dictionary with all parameters plus the computed hash
    """
    # Create a sorted list of key=value pairs
    data_check_string = '\n'.join(sorted(f'{x}={y}' for x, y in params.items() if x not in ('hash')))

    # Compute the SHA256 HMAC hash

    computed_hash = hmac.new(BOT_TOKEN_HASH.digest(), data_check_string.encode(), 'sha256').hexdigest()

    # Return a new dict with all original params plus the hash
    encoded_params = params.copy()
    encoded_params['hash'] = computed_hash
    return encoded_params
