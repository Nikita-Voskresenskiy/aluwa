import json
import os
import time
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram import F
from aiogram.client.default import DefaultBotProperties

from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from requests import send_authenticated_post_request, send_locations
from auth import encode_token

from env_settings import EnvSettings
env = EnvSettings()






# Initialize bot with default properties
bot = Bot(
    token=env.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Dictionary to store active sessions
active_sessions = {}



class LocationSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.is_active = True
        self.filename = f"location_sessions/location_session_{user_id}_{int(time.time())}.json"
        self.locations = []
        self.last_location = None
        self.task = None

    async def start_recording(self):
        """Start periodic recording every 10 seconds"""
        while self.is_active:
            if self.last_location:
                current_time = time.time()
                self.locations.append({
                    "device_timestamp": datetime.fromtimestamp(current_time).isoformat(),
                    "session_id": 3,
                    "latitude": self.last_location.latitude,
                    "longitude": self.last_location.longitude#,
                    #"user_id": self.user_id
                })
                print(self.locations[-1])
                #await send_authenticated_post_request(self.locations[-1], encode_token({'user_id': self.user_id}))
                await send_locations(self.locations[-1], encode_token({'user_id': self.user_id}))
                self.save_to_file()
            await asyncio.sleep(10)

    def update_location(self, location):
        """Update the latest location data"""
        self.last_location = location

    def save_to_file(self):
        """Save current locations to file"""
        with open(self.filename, 'w') as f:
            json.dump(self.locations, f, indent=4)

    async def stop(self):
        """Stop the recording session"""
        self.is_active = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.locations:
            self.save_to_file()


'''
@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("Hi! Send me your live location to start tracking. Use /stop_session to stop tracking.")

'''
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Create a keyboard with a button to request live location


    await message.answer(
        "Please share your live location"
    )

@dp.message(Command("stop_session"))
async def stop_session(message: Message):
    user_id = message.from_user.id
    if user_id in active_sessions:
        session = active_sessions[user_id]
        await session.stop()
        del active_sessions[user_id]
        await message.answer("Location tracking stopped. Session data saved.")
    else:
        await message.answer("No active session to stop.")


@dp.message(F.location.live_period)
async def handle_live_location(message: Message):
    user_id = message.from_user.id
    location = message.location

    # Check if user already has an active session
    if user_id in active_sessions:
        session = active_sessions[user_id]
        if session.is_active:
            await message.answer("You already have an active session. Use /stop_session to stop it first.")
            return

    # Create new session
    session = LocationSession(user_id)
    session.update_location(location)
    session.task = asyncio.create_task(session.start_recording())
    active_sessions[user_id] = session

    await message.answer(
        f"New tracking session started! Data will be saved to {session.filename}. Use /stop_session to stop.")


@dp.message(F.location)
@dp.edited_message(F.location) #needed to receive updates
async def handle_location_update(message: Message):
    user_id = message.from_user.id
    location = message.location

    if user_id in active_sessions and active_sessions[user_id].is_active:
        session = active_sessions[user_id]
        session.update_location(location)

async def on_startup(dispatcher):
    # Create a directory for session files if it doesn't exist
    os.makedirs("location_sessions", exist_ok=True)
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