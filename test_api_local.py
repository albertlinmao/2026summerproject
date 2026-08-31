import httpx
import asyncio

async def test_api():
    async with httpx.AsyncClient(base_url='http://localhost:8000') as client:
        # Assuming the backend is not running, let's just inspect the results_browser.py logic
        pass

if __name__ == '__main__':
    asyncio.run(test_api())
