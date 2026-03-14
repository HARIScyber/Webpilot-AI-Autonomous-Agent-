#!/usr/bin/env python3
"""
test_api_key.py - Test TinyFish API key with exact curl equivalent
=================================================================
Tests if the API key is valid by making the same request as the curl command.

Run: python test_api_key.py
"""

import httpx

def test_api_key():
    """Test the TinyFish API with the exact curl parameters."""
    
    api_key = "sk-tinyfish-AjmIrvlo3dIHxlZ2SEZcKgiTaRyTMIGL"
    url = "https://agent.tinyfish.ai/v1/automation/run-sse"
    
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    
    payload = {
        "url": "https://tinyfish.ai",
        "goal": "Find all open jobs at TinyFish (about page). Respond in json format: { result: [] }",
    }
    
    print("=" * 70)
    print("Testing TinyFish API Key")
    print("=" * 70)
    print(f"Endpoint: {url}")
    print(f"API Key: {api_key[:20]}...{api_key[-5:]}")
    print(f"Target URL: {payload['url']}")
    print()
    
    try:
        print("📤 Sending request...")
        with httpx.stream("POST", url, headers=headers, json=payload, timeout=30) as response:
            print(f"✅ Connected! Status: {response.status_code}")
            print()
            
            if response.status_code != 200:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                try:
                    error_text = response.text
                    print(f"Response: {error_text[:500]}")
                except:
                    pass
                return False
            
            print("📥 Streaming response:")
            print("-" * 70)
            
            event_count = 0
            for line in response.iter_lines():
                if line:
                    event_count += 1
                    print(line[:200])  # Print first 200 chars of each line
                    if event_count >= 10:
                        print("... (more events)")
                        break
            
            print("-" * 70)
            print(f"✅ Success! API key is valid. Received {event_count}+ events")
            return True
            
    except httpx.ConnectError as e:
        print(f"❌ Connection Error: {e}")
        print("   Check your internet connection")
        return False
    except httpx.TimeoutException:
        print(f"❌ Timeout: Request took too long")
        return False
    except httpx.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_api_key()
    print()
    if success:
        print("🎉 Your TinyFish API key is working!")
        print()
        print("Next steps:")
        print("  1. Restart your backend server (Ctrl+C, then uvicorn main:app --reload)")
        print("  2. Run: python run_agent_example.py --example price")
    else:
        print("⚠️  API key test failed. Possible issues:")
        print("  - API key is invalid or expired")
        print("  - No internet connection")
        print("  - TinyFish API is down")
        print()
        print("Get a new API key at: https://tinyfish.ai")
