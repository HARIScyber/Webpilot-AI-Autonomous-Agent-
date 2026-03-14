#!/usr/bin/env python3
"""
test_tinyfish.py - Direct TinyFish API test (mirrors JavaScript example)
=========================================================================
Tests the TinyFish API without the full FastAPI stack.
Helpful for debugging authentication issues.

Run: python test_tinyfish.py
"""

import asyncio
import httpx
from config import settings
from httpx_sse import aconnect_sse

async def test_tinyfish():
    """Test TinyFish API with a simple request."""
    
    print(f"Testing TinyFish API...")
    print(f"API Key: {settings.TINYFISH_API_KEY[:20]}...")
    print(f"Endpoint: {settings.TINYFISH_BASE_URL}")
    print()
    
    headers = {
        "X-API-Key": settings.TINYFISH_API_KEY,
        "Content-Type": "application/json",
    }
    
    payload = {
        "url": "https://agentql.com",
        "goal": "Find all AgentQL subscription plans and their prices. Return result in json format",
    }
    
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            print("Sending request to TinyFish...")
            async with aconnect_sse(
                client,
                method="POST",
                url=settings.TINYFISH_BASE_URL,
                headers=headers,
                json=payload,
            ) as event_source:
                
                # Check response status
                print(f"Response Status: {event_source.response.status_code}")
                
                if event_source.response.status_code != 200:
                    print(f"ERROR: {event_source.response.status_code}")
                    try:
                        error_body = await event_source.response.aread()
                        print(f"Response Body: {error_body.decode()}")
                    except:
                        print("(Unable to read error response body)")
                    return
                
                print("Connected! Reading events...")
                print()
                
                event_count = 0
                async for sse in event_source.aiter_sse():
                    event_count += 1
                    print(f"[Event {event_count}]")
                    print(f"  Type: {sse.event or 'PROGRESS'}")
                    print(f"  Data: {sse.data[:100]}..." if len(sse.data or "") > 100 else f"  Data: {sse.data}")
                    print()
                
                print(f"✅ Success! Received {event_count} events")
                
    except httpx.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_tinyfish())
