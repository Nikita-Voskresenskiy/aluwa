from fastapi import FastAPI
import uvicorn
from env_settings import EnvSettings
settings = EnvSettings()

import json
import logging
import urllib.parse
from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates


from auth import auth_router, verify_init_data_is_correct, encode_token, process_token


from fastapi import APIRouter, Depends
from database import get_db
from schemas import LocationCreate
from routines.locations import get_locations_by_session, create_location
from sqlalchemy.ext.asyncio import AsyncSession

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
    if request.url.path.startswith(('/auth/', '/webapp', '/docs')):
        return await call_next(request)

    # Check for Telegram WebApp auth header
    if request.headers.get('X-Telegram-WebApp-Auth') == 'true':
        return await call_next(request)

    response = await call_next(request)
    # Original auth flow for non-Telegram WebApp requests
    url_safe_path = urllib.parse.quote(request.url.path, safe='')
    template_context = {'request': request, 'next_path': url_safe_path}
    login_wall = templates.TemplateResponse('login.html', template_context)

    try:
        token_parts = process_token(request)
        user_id = token_parts.claims['user_id']
    except Exception as e:
        token_parts = False
        logger.error(f"Unexpected error in middleware while processing token: {str(e)}", exc_info=True)

    if not token_parts:
        return login_wall

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
        token = encode_token({'user_id': user_id})
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

@app.post("/message_from_bot")
async def message_from_bot(request: Request):
    logger.info("Received /message_from_bot request")

    try:
        body = await request.body()
        body_str = body.decode()
        logger.debug(f"Raw request body: {body_str}")

        try:
            token_parts = process_token(request)
        except Exception as e:
            token_parts = False
            logger.error(f"Unexpected error in middleware while processing token: {str(e)}", exc_info=True)
        if token_parts:
            user_id = token_parts.claims['user_id']
            response_data = {
            "user_id": user_id
            }


        logger.info("Authentication successful")
        return JSONResponse(response_data)

    except HTTPException:
        raise  # Re-raise already logged HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in message_from_bot: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/locations")
async def create_new_location(
    location_data: LocationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to create a new location record"""
    new_loc = await create_location(
        session=db,
        session_id=location_data.session_id,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
        custom_timestamp=location_data.device_timestamp
    )
    return {"message": "Location created", "id": new_loc.session_id}

@app.get("/locations/{session_id}")
async def get_session_locations(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to get locations for a session"""
    locations = await get_locations_by_session(db, session_id)
    return {"locations": locations}

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)