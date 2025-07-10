import aiohttp
from typing import Dict, Any

from urllib.parse import urlencode

from auth import encode_query_data
from env_settings import env


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

async def get_token(payload):
    headers = {
        "Content-Type": "application/json"
    }

    encoded = encode_query_data(payload)
    query_string = urlencode(encoded)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "{}://{}/auth/token".format(env.PROTOCOL, env.DOMAIN_NAME),
                    params=query_string,
                    headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print('Response:', data)
                    return data
                else:
                    error = await response.text()
                    print(error)

    except Exception as e:
        print(f"⚠️ Request failed: {str(e)}")

async def send_location(payload: Dict, JWT_TOKEN: str):

    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "{}://{}/track/location".format(env.PROTOCOL, env.DOMAIN_NAME),
                    json=payload,
                    headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print('Response:', data)
                    return data
                else:
                    error = await response.text()
                    print(error)

    except Exception as e:
        print(f"⚠️ Request failed: {str(e)}")

async def start_session(payload: Dict, JWT_TOKEN: str):

    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "{}://{}/track/start_session".format(env.PROTOCOL, env.DOMAIN_NAME),
                    json=payload,
                    headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print('Response:', data)
                    return data
                else:
                    error = await response.text()
                    print(error)

    except Exception as e:
        print(f"⚠️ Request failed: {str(e)}")

async def stop_session(payload: Dict, JWT_TOKEN: str):

    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "{}://{}/track/stop_session".format(env.PROTOCOL, env.DOMAIN_NAME),
                    json=payload,
                    headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print('Response:', data)
                    return data
                else:
                    error = await response.text()
                    print(error)

    except Exception as e:
        print(f"⚠️ Request failed: {str(e)}")