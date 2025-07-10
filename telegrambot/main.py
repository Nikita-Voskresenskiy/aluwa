import json
import os
import time
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram import F
from aiogram.client.default import DefaultBotProperties

from aiogram.types import Message, ReplyKeyboardRemove, MenuButtonWebApp, WebAppInfo

from aiogram.filters import Command
from requests import send_location, start_session, stop_session, get_token
from auth import encode_token
from joserfc import jwt

from env_settings import env






# Initialize bot with default properties
bot = Bot(
    token=env.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Dictionary to store active sessions
active_sessions = {}


class TrackSession:
    def __init__(self, telegram_id, start_timestamp, location):
        self.user_id = -1
        self.telegram_id = telegram_id
        self.start_timestamp = start_timestamp
        self.session_id = -1
        self.live_period = location.live_period

        self.is_active = True
        self.is_paused = False

        self.longitude = None
        self.latitude = None
        self.timestamp = None
        self.task = None

        self.update_location(location, start_timestamp)

    async def set_user_id(self):
        try:
            result = await get_token({'telegram_id': self.telegram_id})
            self.user_id = jwt.decode(result["token"], env.JWT_SECRET_KEY).claims["user_id"]
        except Exception as e:
            print(e)

    async def set_session_id(self):
        payload = {
            "start_timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "live_period": self.live_period
        }
        result = await start_session(payload, encode_token({'user_id': self.user_id}))
        self.session_id = result.get("session_id", -1)

    async def record_location(self):
        """Start periodic recording"""
        while self.is_active:
            if self.session_id > 0:
                payload = {
                    "device_timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
                    "session_id": self.session_id,
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "is_paused": self.is_paused
                }
                #print(payload)
                await send_location(payload, encode_token({'user_id': self.user_id}))
                await asyncio.sleep(10)

    def update_location(self, location, timestamp):
        """Update the latest location data"""
        self.longitude = location.longitude
        self.latitude = location.latitude
        self.timestamp = timestamp

    async def stop_session(self):
        """Stop the recording session"""
        self.is_active = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
    def pause_session(self):
        self.is_paused = True

    def continue_session(self):
        self.is_paused = False


'''
@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("Hi! Send me your live location to start tracking. Use /stop_session to stop tracking.")

'''
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Create a keyboard with a button to request live location


    await message.answer(
        "Please share your live location", reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Command("stop_session"))
async def stop_session(message: Message):
    user_id = message.from_user.id
    if user_id in active_sessions:
        session = active_sessions[user_id]
        await session.stop_session()
        del active_sessions[user_id]
        await message.answer("Location tracking stopped. Session data saved.")
    else:
        await message.answer("No active session to stop.")

@dp.message(Command("pause_session"))
async def pause_session(message: Message):
    user_id = message.from_user.id
    if user_id in active_sessions:
        session = active_sessions[user_id]
        session.pause_session()
        await message.answer("Location tracking paused. \n/continue_session to continue \n\n /stop_session to stop.")
    else:
        await message.answer("No active session to pause.")

@dp.message(Command("continue_session"))
async def continue_session(message: Message):
    user_id = message.from_user.id
    if user_id in active_sessions:
        session = active_sessions[user_id]
        session.pause_session()
        await message.answer("Location tracking continued. \n/pause_session to pause \n\n /stop_session to stop.")
    else:
        await message.answer("No active session to pause.")

# session initialisation is here
@dp.message(F.location.live_period)
async def handle_live_location(message: Message):
    update_timestamp = time.time()
    telegram_id = message.from_user.id
    location = message.location

    # Check if user already has an active session
    if telegram_id in active_sessions:
        session = active_sessions[telegram_id]
        if session.is_active:
            await message.answer("You already have an active session. \n /pause_session to pause \n\n /stop_session to stop.")
            return

    # Create new session
    session = TrackSession(telegram_id, update_timestamp, location)
    await session.set_user_id()
    await session.set_session_id()
    session.task = asyncio.create_task(session.record_location())
    active_sessions[telegram_id] = session

    await message.answer(
        f"New tracking session started! \n /pause_session to pause \n\n /stop_session to stop.")


@dp.message(F.location)
@dp.edited_message(F.location) #needed to receive updates
async def handle_location_update(message: Message):
    update_timestamp = time.time()
    user_id = message.from_user.id
    location = message.location

    if user_id in active_sessions and active_sessions[user_id].is_active:
        session = active_sessions[user_id]
        session.update_location(location, update_timestamp)

async def on_startup(dispatcher):
    if env.PROTOCOL == "https":
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Open App",
                web_app=WebAppInfo(url="{}://{}/webapp".format(env.PROTOCOL, env.DOMAIN_NAME))
            )
        )
    print("Bot started")


async def on_shutdown(dispatcher):
    # Stop all active sessions when bot shuts down
    for session in active_sessions.values():
        if session.is_active:
            await session.stop()
    print("Bot stopped")


if __name__ == '__main__':
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    # For polling:
    dp.run_polling(bot, allowed_updates=["message", "edited_message"])