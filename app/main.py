from fastapi import FastAPI
import uvicorn
from env_settings import EnvSettings
settings = EnvSettings()

import json
import logging
import urllib.parse
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates
from joserfc import jwt
from joserfc.errors import JoseError

from auth import auth_router, verify_init_data_is_correct

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI()

templates = Jinja2Templates('html_files')
static_files = StaticFiles(directory='static_files')





app.mount('/auth', auth_router)
#app.mount('/', static_files, name='static')


@app.middleware('http')
async def middleware(request: Request, call_next):


    # Bypass auth for auth routes and webapp routes
    if request.url.path.startswith(('/auth/', '/webapp')):
        return await call_next(request)

    # Check for Telegram WebApp auth header
    if request.headers.get('X-Telegram-WebApp-Auth') == 'true':
        return await call_next(request)

    response = await call_next(request)
    # Original auth flow for non-Telegram WebApp requests
    url_safe_path = urllib.parse.quote(request.url.path, safe='')
    template_context = {'request': request, 'next_path': url_safe_path}
    login_wall = templates.TemplateResponse('login.html', template_context)

    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        return login_wall

    try:
        token_parts = jwt.decode(token, settings.JWT_SECRET_KEY)
    except JoseError:
        return login_wall

    user_id = token_parts.claims['k']
    if user_id != settings.BOT_ADMIN_ID:
        return login_wall

    return response
@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/webapp", response_class=HTMLResponse)
async def webapp_interface(request: Request):
    return templates.TemplateResponse("webapp.html", {"request": request, "title": "Telegram WebApp"})


@app.post("/webapp-auth")
async def webapp_auth(request: Request):
    logger.info("Received webapp-auth request")

    try:
        body = await request.body()
        body_str = body.decode()
        logger.debug(f"Raw request body: {body_str}")

        init_data = dict(urllib.parse.parse_qsl(body_str))
        logger.info(f"Parsed initData: {init_data}")

        if not init_data.get('hash'):
            logger.warning("Missing hash in initData")
            raise HTTPException(status_code=400, detail="Missing authentication hash")

        # Verification
        verification_result = await verify_init_data_is_correct(init_data)
        logger.info(f"Verification result: {verification_result}")

        if not verification_result:
            logger.warning("initData verification failed")
            raise HTTPException(status_code=401, detail="Invalid Telegram authentication")

        # User data extraction
        user_data_str = init_data.get('user', '{}')
        logger.debug(f"Raw user data: {user_data_str}")

        try:
            user_data = json.loads(user_data_str)
            user_id = user_data.get('id')
            logger.info(f"Extracted user ID: {user_id}")

            if not user_id:
                logger.error("User ID not found in initData")
                raise ValueError("User ID not found")

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"User data parsing failed: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid user data in initData")

        # Token generation
        token_payload = {'k': user_id}
        token = jwt.encode({'alg': 'HS256'}, token_payload, settings.JWT_SECRET_KEY)
        logger.info(f"Generated JWT token for user {user_id}")

        response_data = {
            "status": "authenticated",
            "token": token,
            "user_id": user_id
        }

        logger.info("Authentication successful")
        return JSONResponse(response_data)

    except HTTPException:
        raise  # Re-raise already logged HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in webapp_auth: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)