import json
import os
import time
import asyncio
import queue
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram import F
from aiogram.client.default import DefaultBotProperties

from aiogram.types import Message, ReplyKeyboardRemove, MenuButtonWebApp, WebAppInfo, FSInputFile

from aiogram.filters import Command
from requests import send_location, req_start_track, req_stop_track, get_token
from auth import encode_token
from joserfc import jwt

from env_settings import env






# Initialize bot with default properties
bot = Bot(
    token=env.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Dictionary to store active tracks
active_tracks = {}


class Tracktrack:
    def __init__(self, telegram_id, start_timestamp, location):
        self.user_id = -1
        self.telegram_id = telegram_id
        self.start_timestamp = start_timestamp
        self.track_id = -1
        self.live_period = location.live_period

        self.is_active = True
        self.is_paused = False

        self.longitude = None
        self.latitude = None
        self.timestamp = start_timestamp
        self.task = None
        self.queue_payload = queue.Queue()

    async def set_user_id(self):
        try:
            result = await get_token({'telegram_id': self.telegram_id})
            self.user_id = jwt.decode(result["token"], env.JWT_SECRET_KEY).claims["user_id"]
        except Exception as e:
            print(e)

    async def set_track_id(self):
        payload = {
            "start_timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "live_period": self.live_period
        }
        result = await req_start_track(payload, encode_token({'user_id': self.user_id}))
        self.track_id = result.get("track_id", -1)

    async def record_location(self):
        """Start periodic recording"""
        while self.is_active:
            if self.track_id > 0 and not self.queue_payload.empty():
                #print(payload)
                while not self.queue_payload.empty():
                    await send_location(self.queue_payload.get(), encode_token({'user_id': self.user_id}))
                await asyncio.sleep(120)


    def update_location(self, location, timestamp):
        """Update the latest location data"""
        self.longitude = location.longitude
        self.latitude = location.latitude
        self.timestamp = timestamp
        payload = {
            "device_timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "track_id": self.track_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_paused": self.is_paused
        }
        self.queue_payload.put(payload)

    async def stop_track(self):
        """Stop the recording track"""
        self.is_active = False
        while not self.queue_payload.empty():
            await send_location(self.queue_payload.get(), encode_token({'user_id': self.user_id}))
        result = await req_stop_track({"track_id": self.track_id}, encode_token({'user_id': self.user_id}))
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
    def pause_track(self):
        self.is_paused = True

    def continue_track(self):
        self.is_paused = False


'''
@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("Hi! Send me your live location to start tracking. Use /stop_track to stop tracking.")

'''

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Create a keyboard with a button to request live location
    try:
        animation = FSInputFile("example.mp4")  # Path relative to your script
        await message.reply_animation(
            animation,
            caption="Please share your live location"
        )
    except FileNotFoundError:
        await message.reply("Please share your live location")

@dp.message(Command("stop_track"))
async def cmd_stop_track(message: Message):
    user_id = message.from_user.id
    if user_id in active_tracks:
        track = active_tracks[user_id]
        await track.stop_track()
        del active_tracks[user_id]
        await message.answer("Location tracking stopped. Track data saved.")
    else:
        await message.answer("No active track to stop.")

@dp.message(Command("pause_track"))
async def cmd_pause_track(message: Message):
    user_id = message.from_user.id
    if user_id in active_tracks:
        track = active_tracks[user_id]
        track.pause_track()
        await message.answer("Location tracking paused. \n/continue_track to continue \n\n /stop_track to stop.")
    else:
        await message.answer("No active track to pause.")

@dp.message(Command("continue_track"))
async def cmd_continue_track(message: Message):
    user_id = message.from_user.id
    if user_id in active_tracks:
        track = active_tracks[user_id]
        track.continue_track()
        await message.answer("Location tracking continued. \n/pause_track to pause \n\n /stop_track to stop.")
    else:
        await message.answer("No active track to pause.")

# track initialisation is here
@dp.message(F.location.live_period)
async def handle_live_location(message: Message):
    update_timestamp = time.time()
    telegram_id = message.from_user.id
    location = message.location

    # Check if user already has an active track
    if telegram_id in active_tracks:
        track = active_tracks[telegram_id]
        if track.is_active:
            await message.answer("You already have an active track. \n /pause_track to pause \n\n /stop_track to stop.")
            return

    # Create new track
    track = Tracktrack(telegram_id, update_timestamp, location)
    await track.set_user_id()
    await track.set_track_id()
    track.update_location(location, update_timestamp)

    # start task to send data to backend
    track.task = asyncio.create_task(track.record_location())
    active_tracks[telegram_id] = track

    await message.answer(
        f"New track started! \n /pause_track to pause \n\n /stop_track to stop.")


@dp.message(F.location)
async def handle_current_location(message: Message):
    try:
        animation = FSInputFile("example.mp4")  # Path relative to your script
        await message.reply_animation(
            animation,
            caption="❗️ Please share your live location, not current location."
        )
    except FileNotFoundError:
        await message.reply("❗️ Please share your live location, not current location.")

@dp.message(F.location)
@dp.edited_message(F.location) #needed to receive updates
async def handle_location_update(message: Message):
    update_timestamp = time.time()
    user_id = message.from_user.id
    location = message.location

    if user_id in active_tracks and active_tracks[user_id].is_active:
        track = active_tracks[user_id]
        track.update_location(location, update_timestamp)

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
    # Stop all active tracks when bot shuts down
    for track in active_tracks.values():
        if track.is_active:
            await track.stop()
    print("Bot stopped")


if __name__ == '__main__':
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    # For polling:
    dp.run_polling(bot, allowed_updates=["message", "edited_message"])