from env_settings import env
import logging
import hashlib
from typing import Annotated

from fastapi import APIRouter, Query, status, HTTPException
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from joserfc import jwt
from joserfc.errors import JoseError

BOT_TOKEN_HASH = hashlib.sha256(env.BOT_TOKEN.encode())


auth_router = APIRouter()

import hmac
import hashlib
from typing import Dict, Any

logger = logging.getLogger('telegram.verification')
logger.setLevel(logging.DEBUG)
async def verify_init_data_is_correct(init_data: Dict[str, Any]) -> bool:
    """
    Verify Telegram WebApp initData authentication

    Args:
        init_data: Dictionary containing the parsed initData parameters

    Returns:
        bool: True if verification succeeds, False otherwise
    """
    logger.info("Starting Telegram WebApp initData verification")

    try:
        # 1. Extract and validate hash
        if not (received_hash := init_data.get('hash')):
            logger.error("No hash parameter found in initData")
            return False

        # 2. Prepare data check string
        data_check_items = []
        for key, value in init_data.items():
            if key != 'hash' and value is not None:
                data_check_items.append(f"{key}={value}")

        # Sort parameters alphabetically
        data_check_string = "\n".join(sorted(data_check_items))
        logger.debug(f"Data check string: {data_check_string}")

        # 3. Compute secret key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=env.BOT_TOKEN.encode(),
            digestmod=hashlib.sha256
        ).digest()

        # 4. Compute expected hash
        computed_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        logger.debug(f"Computed hash: {computed_hash}")
        logger.debug(f"Received hash: {received_hash}")

        # 5. Compare hashes
        if not hmac.compare_digest(computed_hash, received_hash):
            logger.error("Hash verification failed")
            logger.error(f"Expected: {computed_hash}")
            logger.error(f"Received: {received_hash}")
            return False

        logger.info("Telegram WebApp verification successful")
        return True

    except Exception as e:
        logger.error(f"Verification error: {str(e)}", exc_info=True)
        return False

def process_token(request: Request):
    token = request.cookies.get(env.COOKIE_NAME)
    if token:
        logger.debug(f"Cookie. JWT: {token}")
    if not token:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return False
        token = auth_header.split(" ")[1]
        logger.debug(f"Bearer. JWT: {token}")

    token_parts = False
    try:
        token_parts = jwt.decode(token, env.JWT_SECRET_KEY)
        return token_parts
    except JoseError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Authorization header",
        )


def encode_token(payload: Dict):
    return jwt.encode({'alg': 'HS256'}, payload, env.JWT_SECRET_KEY)

async def verify_query_is_correct(params, query_hash):
    data_check_string = '\n'.join(sorted(f'{x}={y}' for x, y in params if x not in ('hash', 'next')))
    computed_hash = hmac.new(BOT_TOKEN_HASH.digest(), data_check_string.encode(), 'sha256').hexdigest()
    return hmac.compare_digest(computed_hash, query_hash)

@auth_router.get('/telegram-callback')
async def telegram_callback(
        request: Request,
        user_id: Annotated[int, Query(alias='id')],
        query_hash: Annotated[str, Query(alias='hash')],
        next_url: Annotated[str, Query(alias='next')] = '/',
):
    params = request.query_params.items()

    if not await verify_query_is_correct(params, query_hash):
        return PlainTextResponse('Authorization failed. Please try again', status_code=401)

    token = encode_token({'user_id': user_id})
    response = RedirectResponse(next_url)
    response.set_cookie(key=env.COOKIE_NAME, value=token, secure=True, samesite='lax', httponly=True)
    return response


@auth_router.get('/logout')
async def logout():
    response = RedirectResponse('/')
    response.delete_cookie(key=env.COOKIE_NAME)
    return response