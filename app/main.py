from fastapi import FastAPI
import uvicorn
from env_settings import env
from app_logger import logger

import json
import urllib.parse
from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates


from auth import auth_router, verify_init_data_is_correct, encode_token, process_token


from fastapi import APIRouter, Depends
from database import get_db
from schemas import RecordLocation, CreateTrackSession
from queries.locations import get_sessions_by_telegram_id, get_coordinates_by_session_id, record_location, start_session
from sqlalchemy.ext.asyncio import AsyncSession


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

    # Original auth flow for non-Telegram WebApp requests
    url_safe_path = urllib.parse.quote(request.url.path, safe='')
    template_context = {'request': request, 'next_path': url_safe_path, 'bot_username': env.BOT_USERNAME}
    login_wall = templates.TemplateResponse('login.html', template_context)

    try:
        token_parts = process_token(request)
    except Exception as e:
        token_parts = False
        logger.error(f"Unexpected error in middleware while processing token: {str(e)}", exc_info=True)

    if not token_parts:
        return login_wall
    try:
        telegram_id = token_parts.claims['telegram_id']
        request.state.telegram_id = telegram_id
        #if request.state.telegram_id != env.BOT_ADMIN_ID:
        #    return login_wall
    except:
        return login_wall

    return await call_next(request)
@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI!"}


@app.get("/webapp", response_class=HTMLResponse)
async def webapp_interface(request: Request):
    #return templates.TemplateResponse("webapp.html", {"request": request, "title": "Telegram WebApp"})
    return templates.TemplateResponse("trackpage.html", {"request": request, "title": "Telegram WebApp", 'cookie_name': env.COOKIE_NAME})

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
            telegram_id = user_data.get('id')
            logger.info(f"Extracted user ID: {telegram_id}")

            if not telegram_id:
                logger.error("User ID not found in initData")
                raise ValueError("User ID not found")

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"User data parsing failed: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid user data in initData")

        # Token generation
        token = encode_token({'telegram_id': telegram_id})
        logger.info(f"Generated JWT token for user {telegram_id}")

        response_data = {
            "status": "authenticated",
            "token": token,
            "user_id": telegram_id
        }

        logger.info("Authentication successful")
        return JSONResponse(response_data)

    except HTTPException:
        raise  # Re-raise already logged HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in webapp_auth: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/track/location")
async def record_location_for_session(
    location_data: RecordLocation,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    telegram_id = request.state.telegram_id
    """Endpoint to create a new location record"""
    new_loc = await record_location(session=db, session_id=location_data.session_id, telegram_id=telegram_id, latitude=location_data.latitude,
                                    longitude=location_data.longitude, custom_timestamp=location_data.device_timestamp, is_paused=location_data.is_paused)
    return {"message": "Location added"}


@app.post("/track/start_session")
async def start_new_track_session(
    session_data: CreateTrackSession,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    telegram_id = request.state.telegram_id
    """Endpoint to create a new location record"""
    new_session_id = await start_session(session=db, telegram_id=telegram_id, start_timestamp=session_data.start_timestamp,
                                    live_period=session_data.live_period)
    return {"message": "Session created", "session_id": new_session_id}


@app.get("/track/sessions")
async def start_new_track_session(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        telegram_id = request.state.telegram_id
        """Endpoint to create a new location record"""
        user_sessions = await get_sessions_by_telegram_id(session=db, telegram_id=telegram_id)
        r = [{"session_id": s.session_id,
              "start_timestamp": s.start_timestamp.isoformat(),
              } for s in user_sessions]
    except Exception as e:
        return {"error": True, "message": e}

    return {"error": False, "result": json.dumps(r)}

@app.get("/track/sessions/{session_id}/coordinates")
async def start_new_track_session(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        telegram_id = request.state.telegram_id
        """Endpoint to create a new location record"""
        coordinates = await get_coordinates_by_session_id(session=db, track_session_id=session_id, telegram_id=telegram_id)
        processed_coordinates = [{
            "lon": c[0],
            "lat": c[1],
            "t": c[2].isoformat(),
            "p": c[3]
        }
        for c in coordinates]

    except Exception as e:
        return {"error": True, "message": e}

    return {"error": False, "result": json.dumps(processed_coordinates)}

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)