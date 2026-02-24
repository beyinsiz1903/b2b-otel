#!/usr/bin/env python3
"""
Comprehensive WebSocket Real-time Notifications Backend Testing
Test file for CapX Platform WebSocket functionality
"""

import asyncio
import json
import time
import traceback
from typing import Optional, Dict, Any

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException


class WebSocketTester:
    def __init__(self, backend_url: str):
        """
        Initialize WebSocket tester with backend URL.
        Args:
            backend_url: Base backend URL (e.g., "https://improvement-guide-2.preview.emergentagent.com")
        """
        self.backend_url = backend_url
        self.ws_url = backend_url.replace("https://", "wss://").replace("http://", "ws://")
        self.jwt_token: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_results = []

    def log_test(self, test_name: str, status: str, details: str = "", error: str = ""):
        """Log test result"""
        result = {
            "test_name": test_name,
            "status": status,
            "details": details,
            "error": error,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏭️"
        print(f"{status_icon} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
        if error:
            print(f"   Error: {error}")

    async def login(self) -> bool:
        """Login to get JWT token"""
        try:
            login_data = aiohttp.FormData()
            login_data.add_field('username', 'admin@test.com')
            login_data.add_field('password', 'Admin123')

            async with self.session.post(f"{self.backend_url}/api/auth/login", data=login_data) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.jwt_token = data.get("access_token")
                    self.log_test("Login Authentication", "PASS", f"Successfully logged in, token length: {len(self.jwt_token) if self.jwt_token else 0}")
                    return True
                else:
                    error_text = await resp.text()
                    self.log_test("Login Authentication", "FAIL", f"Status: {resp.status}", error_text)
                    return False
        except Exception as e:
            self.log_test("Login Authentication", "FAIL", "", str(e))
            return False

    async def test_websocket_connection(self) -> bool:
        """Test 1: WebSocket Connection - verify connected and unread_count messages"""
        try:
            if not self.jwt_token:
                self.log_test("WebSocket Connection", "FAIL", "", "No JWT token available")
                return False

            uri = f"{self.ws_url}/api/ws/notifications?token={self.jwt_token}"
            
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
                # Should receive 'connected' message first
                message1 = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                msg1_data = json.loads(message1)
                
                if msg1_data.get("type") != "connected":
                    self.log_test("WebSocket Connection", "FAIL", f"Expected 'connected' type, got: {msg1_data.get('type')}", "")
                    return False

                connected_data = msg1_data.get("data", {})
                required_fields = ["hotel_id", "hotel_name", "message"]
                missing_fields = [field for field in required_fields if field not in connected_data]
                
                if missing_fields:
                    self.log_test("WebSocket Connection", "FAIL", f"Missing fields in connected message: {missing_fields}", "")
                    return False

                # Should receive 'unread_count' message second
                message2 = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                msg2_data = json.loads(message2)
                
                if msg2_data.get("type") != "unread_count":
                    self.log_test("WebSocket Connection", "FAIL", f"Expected 'unread_count' type, got: {msg2_data.get('type')}", "")
                    return False

                unread_data = msg2_data.get("data", {})
                if "count" not in unread_data:
                    self.log_test("WebSocket Connection", "FAIL", "Missing 'count' field in unread_count message", "")
                    return False

                self.log_test("WebSocket Connection", "PASS", 
                             f"Hotel: {connected_data['hotel_name']}, Unread count: {unread_data['count']}")
                return True

        except asyncio.TimeoutError:
            self.log_test("WebSocket Connection", "FAIL", "", "Timeout waiting for WebSocket messages")
            return False
        except Exception as e:
            self.log_test("WebSocket Connection", "FAIL", "", str(e))
            return False

    async def test_ping_pong(self) -> bool:
        """Test 2: Ping/Pong functionality"""
        try:
            uri = f"{self.ws_url}/api/ws/notifications?token={self.jwt_token}"
            
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
                # Skip initial messages
                await websocket.recv()  # connected
                await websocket.recv()  # unread_count
                
                # Send ping
                ping_message = {"type": "ping"}
                await websocket.send(json.dumps(ping_message))
                
                # Should receive pong
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                pong_data = json.loads(response)
                
                if pong_data.get("type") != "pong":
                    self.log_test("Ping/Pong", "FAIL", f"Expected 'pong' type, got: {pong_data.get('type')}", "")
                    return False

                pong_payload = pong_data.get("data", {})
                if "timestamp" not in pong_payload:
                    self.log_test("Ping/Pong", "FAIL", "Missing 'timestamp' field in pong response", "")
                    return False

                self.log_test("Ping/Pong", "PASS", f"Pong timestamp: {pong_payload['timestamp']}")
                return True

        except Exception as e:
            self.log_test("Ping/Pong", "FAIL", "", str(e))
            return False

    async def test_get_unread_count(self) -> bool:
        """Test 3: Get Unread Count"""
        try:
            uri = f"{self.ws_url}/api/ws/notifications?token={self.jwt_token}"
            
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
                # Skip initial messages
                await websocket.recv()  # connected
                await websocket.recv()  # unread_count
                
                # Send get_unread_count request
                request_message = {"type": "get_unread_count"}
                await websocket.send(json.dumps(request_message))
                
                # Should receive unread_count response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                count_data = json.loads(response)
                
                if count_data.get("type") != "unread_count":
                    self.log_test("Get Unread Count", "FAIL", f"Expected 'unread_count' type, got: {count_data.get('type')}", "")
                    return False

                count_payload = count_data.get("data", {})
                if "count" not in count_payload:
                    self.log_test("Get Unread Count", "FAIL", "Missing 'count' field in response", "")
                    return False

                self.log_test("Get Unread Count", "PASS", f"Unread count: {count_payload['count']}")
                return True

        except Exception as e:
            self.log_test("Get Unread Count", "FAIL", "", str(e))
            return False

    async def test_real_time_notification_push(self) -> bool:
        """Test 4: Real-time Notification Push - trigger notification via REST API while connected via WebSocket"""
        try:
            uri = f"{self.ws_url}/api/ws/notifications?token={self.jwt_token}"
            
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
                # Skip initial messages
                await websocket.recv()  # connected
                await websocket.recv()  # unread_count
                
                # Trigger a notification via REST API (subscription)
                subscription_data = {
                    "plan_id": "premium",
                    "billing_cycle": "monthly"
                }
                
                headers = {"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"}
                
                async with self.session.post(f"{self.backend_url}/api/subscriptions/subscribe", 
                                           json=subscription_data, headers=headers) as resp:
                    if resp.status not in [200, 201]:
                        # Try alternative notification trigger
                        payment_data = {"match_id": "dummy_match", "method": "credit_card"}
                        async with self.session.post(f"{self.backend_url}/api/payments/initiate", 
                                                   json=payment_data, headers=headers) as pay_resp:
                            pass  # May fail, but should still generate notification
                
                # Wait for real-time notification via WebSocket
                try:
                    notification_message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    notif_data = json.loads(notification_message)
                    
                    if notif_data.get("type") != "notification":
                        self.log_test("Real-time Notification Push", "FAIL", 
                                     f"Expected 'notification' type, got: {notif_data.get('type')}", "")
                        return False

                    notif_payload = notif_data.get("data", {})
                    required_fields = ["title", "message", "type"]
                    missing_fields = [field for field in required_fields if field not in notif_payload]
                    
                    if missing_fields:
                        self.log_test("Real-time Notification Push", "FAIL", 
                                     f"Missing fields in notification: {missing_fields}", "")
                        return False

                    self.log_test("Real-time Notification Push", "PASS", 
                                 f"Title: {notif_payload['title']}, Type: {notif_payload['type']}")
                    return True
                    
                except asyncio.TimeoutError:
                    self.log_test("Real-time Notification Push", "FAIL", "", 
                                 "Timeout waiting for real-time notification - REST API trigger may not have worked")
                    return False

        except Exception as e:
            self.log_test("Real-time Notification Push", "FAIL", "", str(e))
            return False

    async def test_mark_all_read(self) -> bool:
        """Test 5: Mark All Read via WebSocket"""
        try:
            uri = f"{self.ws_url}/api/ws/notifications?token={self.jwt_token}"
            
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
                # Skip initial messages
                await websocket.recv()  # connected
                await websocket.recv()  # unread_count
                
                # Send mark_all_read request
                mark_all_message = {"type": "mark_all_read"}
                await websocket.send(json.dumps(mark_all_message))
                
                # Should receive unread_count response with count=0
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                count_data = json.loads(response)
                
                if count_data.get("type") != "unread_count":
                    self.log_test("Mark All Read", "FAIL", f"Expected 'unread_count' type, got: {count_data.get('type')}", "")
                    return False

                count_payload = count_data.get("data", {})
                if count_payload.get("count") != 0:
                    self.log_test("Mark All Read", "FAIL", f"Expected count=0, got: {count_payload.get('count')}", "")
                    return False

                self.log_test("Mark All Read", "PASS", "All notifications marked as read, count=0")
                return True

        except Exception as e:
            self.log_test("Mark All Read", "FAIL", "", str(e))
            return False

    async def test_websocket_status_api(self) -> bool:
        """Test 6: WebSocket Status API (admin only)"""
        try:
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
            
            async with self.session.get(f"{self.backend_url}/api/ws/status", headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    self.log_test("WebSocket Status API", "FAIL", f"Status: {resp.status}", error_text)
                    return False

                data = await resp.json()
                
                required_fields = ["online_connections", "online_hotels"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("WebSocket Status API", "FAIL", f"Missing fields: {missing_fields}", "")
                    return False

                self.log_test("WebSocket Status API", "PASS", 
                             f"Online connections: {data['online_connections']}, Hotels: {len(data['online_hotels'])}")
                return True

        except Exception as e:
            self.log_test("WebSocket Status API", "FAIL", "", str(e))
            return False

    async def test_invalid_token(self) -> bool:
        """Test 7: Invalid Token - connection should be rejected"""
        try:
            invalid_token = "invalid-token-xyz"
            uri = f"{self.ws_url}/api/ws/notifications?token={invalid_token}"
            
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
                    # If we reach here, the connection was not rejected as expected
                    self.log_test("Invalid Token", "FAIL", "Connection was accepted with invalid token", "")
                    return False
            except WebSocketException as e:
                # Check if it's the expected rejection (close code 4001)
                if "4001" in str(e) or "Token gerekli" in str(e) or "Geçersiz" in str(e):
                    self.log_test("Invalid Token", "PASS", f"Connection rejected as expected: {e}")
                    return True
                else:
                    self.log_test("Invalid Token", "FAIL", f"Unexpected error: {e}", "")
                    return False

        except Exception as e:
            # Check if the error indicates proper rejection
            if "4001" in str(e) or "token" in str(e).lower() or "geçersiz" in str(e).lower():
                self.log_test("Invalid Token", "PASS", f"Connection rejected as expected: {e}")
                return True
            else:
                self.log_test("Invalid Token", "FAIL", "", str(e))
                return False

    async def test_existing_endpoints(self) -> bool:
        """Test 8: Verify existing endpoints still work"""
        try:
            endpoints = [
                ("/api/stats", True),  # requires auth
                ("/api/performance/health", False),  # no auth
                ("/api/regions", True)  # requires auth
            ]
            
            all_passed = True
            results = []
            
            for endpoint, requires_auth in endpoints:
                headers = {"Authorization": f"Bearer {self.jwt_token}"} if requires_auth else {}
                
                try:
                    async with self.session.get(f"{self.backend_url}{endpoint}", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results.append(f"{endpoint}: ✅ ({resp.status})")
                            
                            # Special check for regions endpoint
                            if endpoint == "/api/regions" and isinstance(data, list):
                                if len(data) != 6:
                                    results.append(f"  ⚠️ Expected 6 regions, got {len(data)}")
                                else:
                                    results.append(f"  ✅ All 6 regions returned")
                        else:
                            error_text = await resp.text()
                            results.append(f"{endpoint}: ❌ ({resp.status}) {error_text[:100]}")
                            all_passed = False
                except Exception as e:
                    results.append(f"{endpoint}: ❌ Exception: {str(e)[:100]}")
                    all_passed = False
            
            status = "PASS" if all_passed else "FAIL"
            self.log_test("Existing Endpoints", status, "; ".join(results))
            return all_passed

        except Exception as e:
            self.log_test("Existing Endpoints", "FAIL", "", str(e))
            return False

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all WebSocket tests"""
        print("🚀 Starting WebSocket Real-time Notifications Backend Testing")
        print("=" * 70)
        
        # Initialize HTTP session
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(connector=connector)
        
        try:
            # Login first
            if not await self.login():
                return {"success": False, "error": "Failed to login"}

            # Run all tests
            tests = [
                self.test_websocket_connection,
                self.test_ping_pong, 
                self.test_get_unread_count,
                self.test_real_time_notification_push,
                self.test_mark_all_read,
                self.test_websocket_status_api,
                self.test_invalid_token,
                self.test_existing_endpoints
            ]
            
            passed = 0
            failed = 0
            
            for test_func in tests:
                try:
                    result = await test_func()
                    if result:
                        passed += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"❌ Test {test_func.__name__} crashed: {e}")
                    failed += 1
                    self.log_test(test_func.__name__, "FAIL", "", f"Test crashed: {e}")
                
                # Small delay between tests
                await asyncio.sleep(0.5)

            # Summary
            print("\n" + "=" * 70)
            print(f"📊 TEST SUMMARY")
            print(f"✅ PASSED: {passed}")
            print(f"❌ FAILED: {failed}")
            print(f"📈 SUCCESS RATE: {passed/(passed+failed)*100:.1f}%" if (passed+failed) > 0 else "0%")
            
            return {
                "success": failed == 0,
                "passed": passed,
                "failed": failed,
                "total": passed + failed,
                "success_rate": passed/(passed+failed)*100 if (passed+failed) > 0 else 0,
                "test_results": self.test_results
            }

        finally:
            await self.session.close()


async def main():
    """Main function to run WebSocket tests"""
    try:
        # Use the backend URL from frontend/.env
        backend_url = "https://improvement-guide-2.preview.emergentagent.com"
        
        tester = WebSocketTester(backend_url)
        results = await tester.run_all_tests()
        
        if results["success"]:
            print(f"\n🎉 ALL TESTS PASSED! WebSocket functionality is working perfectly.")
        else:
            print(f"\n⚠️ Some tests failed. Please check the details above.")
            
        return results
        
    except Exception as e:
        print(f"❌ Testing framework error: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    results = asyncio.run(main())