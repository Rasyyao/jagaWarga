import asyncio
from shared.wa_client import send_text_message

async def test():
    result = await send_text_message(
        phone="6285746156216",   
        message="Test JagaWarga! 🛡️"
    )
    print(result)

asyncio.run(test())