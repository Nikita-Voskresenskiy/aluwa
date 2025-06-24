import aiohttp
from typing import Dict, Any

from env_settings import EnvSettings
env = EnvSettings()


async def send_authenticated_post_request(payload: Dict, JWT_TOKEN: str):
    """
    Sends a POST request with JWT authorization.
    Trigger with command: /post_example
    """
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }


    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "{}://{}/message_from_bot".format(env.PROTOCOL, env.DOMAIN_NAME),
                    json=payload,
                    headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print('Response:', data)
                else:
                    error = await response.text()
                    print(error)

    except Exception as e:
        print(f"⚠️ Request failed: {str(e)}")

async def send_locations(payload: Dict, JWT_TOKEN: str):
    """
    Sends a POST request with JWT authorization.
    Trigger with command: /post_example
    """
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }


    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "{}://{}/locations".format(env.PROTOCOL, env.DOMAIN_NAME),
                    json=payload,
                    headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print('Response:', data)
                else:
                    error = await response.text()
                    print(error)

    except Exception as e:
        print(f"⚠️ Request failed: {str(e)}")


