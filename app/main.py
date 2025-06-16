from fastapi import FastAPI
import uvicorn
from env_settings import EnvSettings
settings = EnvSettings()



import urllib.parse
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates
from joserfc import jwt
from joserfc.errors import JoseError

from auth import auth_router


app = FastAPI()

templates = Jinja2Templates('html_files')
static_files = StaticFiles(directory='static_files')


@app.get("/")
async def read_root():
    return {"message": "Hello from FastAPI!"}



app.mount('/auth', auth_router)
app.mount('/', static_files, name='static')


@app.middleware('http')
async def middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/auth/'):
        return response

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


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)