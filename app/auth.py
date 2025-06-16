from env_settings import EnvSettings
settings = EnvSettings()

import hmac
import hashlib
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from joserfc import jwt

BOT_TOKEN_HASH = hashlib.sha256(settings.BOT_TOKEN.encode())


auth_router = APIRouter()

async def verify_query_is_correct(params):
    data_check_string = '\n'.join(sorted(f'{x}={y}' for x, y in params if x not in ('hash', 'next')))
    computed_hash = hmac.new(BOT_TOKEN_HASH.digest(), data_check_string.encode(), 'sha256').hexdigest()
    return hmac.compare_digest(computed_hash, params.query_hash)

@auth_router.get('/telegram-callback')
async def telegram_callback(
        request: Request,
        user_id: Annotated[int, Query(alias='id')],
        query_hash: Annotated[str, Query(alias='hash')],
        next_url: Annotated[str, Query(alias='next')] = '/',
):
    params = request.query_params.items()

    if not verify_query_is_correct(params):
        return PlainTextResponse('Authorization failed. Please try again', status_code=401)

    token = jwt.encode({'alg': 'HS256'}, {'k': user_id}, settings.JWT_SECRET_KEY)
    response = RedirectResponse(next_url)
    response.set_cookie(key=settings.COOKIE_NAME, value=token)
    return response


@auth_router.get('/logout')
async def logout():
    response = RedirectResponse('/')
    response.delete_cookie(key=settings.COOKIE_NAME)
    return response