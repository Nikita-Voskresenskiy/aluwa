from fastapi import FastAPI
import uvicorn
from env_settings import env
from app_logger import logger

import json
import urllib.parse
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates


from auth import auth_router, verify_init_data_is_correct, encode_token, process_token


from fastapi import Depends
from database import get_db
from schemas import RecordLocation, CreateTrack, StopTrack
from queries.locations import get_tracks_by_user_id, get_coordinates_by_track_id, record_location, start_track, calculate_speeds_for_track, calculate_track_statistics
from queries.db_user_access import get_user_id_by_telegram_id
from sqlalchemy.ext.asyncio import AsyncSession


app = FastAPI()

templates = Jinja2Templates('html_files')
static_files = StaticFiles(directory='static_files')





app.mount('/auth', auth_router)
#app.mount('/', static_files, name='static')


@app.middleware('http')
async def middleware(request: Request, call_next):
    # Bypass auth for auth routes, static files, and docs
    if request.url.path.startswith(('/auth', '/webapp', '/docs', '/openapi.json')):
        return await call_next(request)

    # Handle WebApp flow
    if request.headers.get('X-Telegram-WebApp-Auth') == 'true':
        # WebApp-specific checks
        return await call_next(request)

    # Browser flow - check for cookie auth
    try:
        token_parts = process_token(request)
        if token_parts:
            request.state.user_id = token_parts.claims['user_id']
            return await call_next(request)
    except Exception as e:
        logger.error(f"Error processing token: {str(e)}", exc_info=True)

    # Not authenticated - show login wall
    url_safe_path = urllib.parse.quote(request.url.path, safe='')
    return templates.TemplateResponse('login.html', {
        'request': request,
        'next_path': url_safe_path,
        'bot_username': env.BOT_USERNAME
    })
@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI!"}


@app.get("/webapp", response_class=HTMLResponse)
async def webapp_interface(request: Request):
    #return templates.TemplateResponse("webapp.html", {"request": request, "title": "Telegram WebApp"})
    return templates.TemplateResponse("trackpage.html", {"request": request, "title": "Telegram WebApp"})

@app.post("/webapp-auth")
async def webapp_auth(request: Request, 
                      db: AsyncSession = Depends(get_db)
                      ):
    logger.info("Received webapp-auth request")

    try:
        body = await request.body()
        body_str = body.decode()
        logger.debug(f"Raw request body: {body_str}")

        init_data = dict(urllib.parse.parse_qsl(body_str))
        logger.info(f"Parsed initData: {init_data}")
        #'''
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
        #'''
        user_id = await get_user_id_by_telegram_id(session=db, telegram_id=telegram_id)
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

@app.post("/track/location")
async def record_location_for_track(
    location_data: RecordLocation,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = request.state.user_id
    """Endpoint to create a new location record"""
    new_loc = await record_location(session=db, track_id=location_data.track_id, user_id=user_id, latitude=location_data.latitude,
                                    longitude=location_data.longitude, custom_timestamp=location_data.device_timestamp, is_paused=location_data.is_paused)
    return {"message": "Location added"}


@app.post("/track/start_track")
async def start_new_track(
    track_data: CreateTrack,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = request.state.user_id
    """Endpoint to create a new location record"""
    new_track_id = await start_track(session=db, user_id=user_id, start_timestamp=track_data.start_timestamp,
                                    live_period=track_data.live_period)
    return {"message": "Track created", "track_id": new_track_id}


@app.get("/track/tracks")
async def get_user_tracks(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_id = request.state.user_id
        """Endpoint to create a new location record"""
        user_tracks = await get_tracks_by_user_id(session=db, user_id=user_id)
        r = [{"track_id": s.track_id,
              "start_timestamp": s.start_timestamp.isoformat(),
              "distance_m_total": s.distance_m_total,
              "speed_mps_average": s.speed_mps_average,
              "speed_mps_max": s.speed_mps_max,
              "duration_s_active": s.duration_s_active,
              "duration_s_total": s.duration_s_total
              } for s in user_tracks]
    except Exception as e:
        return {"error": True, "message": e}

    return {"error": False, "result": json.dumps(r)}

@app.get("/track/{track_id}/coordinates")
async def get_track_coordinates(
    track_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_id = request.state.user_id
        """Endpoint to create a new location record"""
        coordinates = await get_coordinates_by_track_id(session=db, track_id=track_id, user_id = user_id)
        processed_coordinates = [{
            "lon": c[0],
            "lat": c[1],
            "t": c[2].isoformat(),
            "p": c[3],
            "s": c[4]
        }
        for c in coordinates]

    except Exception as e:
        return {"error": True, "message": e}

    return {"error": False, "result": json.dumps(processed_coordinates)}

@app.post("/track/stop_track")
async def stop_existing_track(
    data: StopTrack,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_id = request.state.user_id
        await calculate_speeds_for_track(session=db, track_id=data.track_id, user_id=user_id)
        statistics = await calculate_track_statistics(session=db, track_id=data.track_id, user_id=user_id)


    except Exception as e:
        return {"error": True, "message": e}

    return {"error": False, "result": statistics}

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)