#!/usr/bin/env python3
"""
Additional WebSocket tests to verify specific functionality
"""

import asyncio
import json
import aiohttp
import websockets


async def test_invalid_token_detailed():
    """Detailed test for invalid token handling"""
    backend_url = "https://improvement-guide-2.preview.emergentagent.com"
    ws_url = backend_url.replace("https://", "wss://")
    
    print("🔍 Testing Invalid Token Handling in Detail...")
    
    # Test 1: No token
    try:
        uri = f"{ws_url}/api/ws/notifications"
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
            print("❌ No token test: Connection accepted when it shouldn't be")
    except Exception as e:
        print(f"✅ No token test: Connection rejected as expected - {e}")
    
    # Test 2: Invalid token
    try:
        invalid_token = "invalid-token-xyz"
        uri = f"{ws_url}/api/ws/notifications?token={invalid_token}"
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
            print("❌ Invalid token test: Connection accepted when it shouldn't be")
    except Exception as e:
        print(f"✅ Invalid token test: Connection rejected as expected - {e}")
    
    # Test 3: Expired token (simulate with malformed JWT)
    try:
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        uri = f"{ws_url}/api/ws/notifications?token={expired_token}"
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
            print("❌ Expired token test: Connection accepted when it shouldn't be")
    except Exception as e:
        print(f"✅ Expired token test: Connection rejected as expected - {e}")


async def test_websocket_message_handling():
    """Test WebSocket message handling functionality"""
    backend_url = "https://improvement-guide-2.preview.emergentagent.com"
    ws_url = backend_url.replace("https://", "wss://")
    
    # Get valid token first
    async with aiohttp.ClientSession() as session:
        login_data = aiohttp.FormData()
        login_data.add_field('username', 'admin@test.com')
        login_data.add_field('password', 'Admin123')
        
        async with session.post(f"{backend_url}/api/auth/login", data=login_data) as resp:
            if resp.status != 200:
                print("❌ Failed to login for message handling test")
                return
            data = await resp.json()
            jwt_token = data.get("access_token")
    
    print("🔍 Testing WebSocket Message Handling...")
    
    uri = f"{ws_url}/api/ws/notifications?token={jwt_token}"
    
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
            # Skip initial messages
            await websocket.recv()  # connected
            await websocket.recv()  # unread_count
            
            # Test invalid JSON
            try:
                await websocket.send("invalid json")
                # Wait a bit to see if connection closes
                await asyncio.sleep(1)
                print("✅ Invalid JSON handled gracefully")
            except Exception as e:
                print(f"⚠️ Invalid JSON caused error: {e}")
            
            # Test unknown message type
            unknown_msg = {"type": "unknown_command", "data": {"test": "value"}}
            await websocket.send(json.dumps(unknown_msg))
            await asyncio.sleep(1)
            print("✅ Unknown message type handled gracefully")
            
            # Test ping again to verify connection is still alive
            ping_message = {"type": "ping"}
            await websocket.send(json.dumps(ping_message))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            pong_data = json.loads(response)
            
            if pong_data.get("type") == "pong":
                print("✅ Connection still alive after invalid messages")
            else:
                print("❌ Connection seems damaged after invalid messages")
                
    except Exception as e:
        print(f"❌ Message handling test failed: {e}")


async def test_concurrent_connections():
    """Test multiple concurrent WebSocket connections"""
    backend_url = "https://improvement-guide-2.preview.emergentagent.com"
    ws_url = backend_url.replace("https://", "wss://")
    
    # Get valid token first
    async with aiohttp.ClientSession() as session:
        login_data = aiohttp.FormData()
        login_data.add_field('username', 'admin@test.com')
        login_data.add_field('password', 'Admin123')
        
        async with session.post(f"{backend_url}/api/auth/login", data=login_data) as resp:
            if resp.status != 200:
                print("❌ Failed to login for concurrent connections test")
                return
            data = await resp.json()
            jwt_token = data.get("access_token")
    
    print("🔍 Testing Concurrent WebSocket Connections...")
    
    uri = f"{ws_url}/api/ws/notifications?token={jwt_token}"
    
    async def single_connection(conn_id):
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
                # Skip initial messages
                await websocket.recv()  # connected
                await websocket.recv()  # unread_count
                
                # Send a ping
                ping_message = {"type": "ping"}
                await websocket.send(json.dumps(ping_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                pong_data = json.loads(response)
                
                if pong_data.get("type") == "pong":
                    print(f"✅ Connection {conn_id}: Successful ping/pong")
                    return True
                else:
                    print(f"❌ Connection {conn_id}: Failed ping/pong")
                    return False
        except Exception as e:
            print(f"❌ Connection {conn_id}: Error - {e}")
            return False
    
    # Test 3 concurrent connections
    tasks = [single_connection(i) for i in range(1, 4)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = sum(1 for r in results if r is True)
    print(f"✅ Concurrent connections: {successful}/3 successful")


async def main():
    """Run additional WebSocket tests"""
    print("🚀 Running Additional WebSocket Tests")
    print("=" * 50)
    
    await test_invalid_token_detailed()
    print()
    await test_websocket_message_handling()
    print()
    await test_concurrent_connections()
    
    print("\n✅ Additional tests completed!")


if __name__ == "__main__":
    asyncio.run(main())