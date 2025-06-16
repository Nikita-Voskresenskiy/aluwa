import aiohttp
from typing import Dict, Any

API_URL = "https://aluwa.ru/message_from_bot"


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
                    API_URL,
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


