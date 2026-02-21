#!/usr/bin/env python3
"""
Comprehensive backend testing for CapX Sapanca-Kartepe hotel capacity sharing platform
Testing all new inventory, pricing, and performance endpoints
"""

import requests
import json
import sys
import time
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://performance-check-4.preview.emergentagent.com/api"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "Admin123"

class CapXTester:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.hotel_id = None
        self.inventory_ids = []
        self.pricing_rule_ids = []
        self.failed_tests = []
        self.passed_tests = []
        
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test results"""
        if passed:
            self.passed_tests.append(test_name)
            print(f"✅ {test_name}")
        else:
            self.failed_tests.append((test_name, message))
            print(f"❌ {test_name}: {message}")
    
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                    auth: bool = True, params: Optional[Dict] = None) -> requests.Response:
        """Make HTTP request with proper headers"""
        url = f"{BASE_URL}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        if method == "GET":
            return self.session.get(url, headers=headers, params=params)
        elif method == "POST":
            return self.session.post(url, headers=headers, json=data)
        elif method == "PUT":
            return self.session.put(url, headers=headers, json=data)
        elif method == "DELETE":
            return self.session.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
    
    def login(self) -> bool:
        """Login and get access token"""
        print("🔐 Testing authentication...")
        
        # Use form data for login
        response = self.session.post(
            f"{BASE_URL}/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            self.hotel_id = data.get("hotel_id")
            self.log_test("Authentication", True)
            return True
        else:
            self.log_test("Authentication", False, f"Status: {response.status_code}")
            return False
    
    def test_inventory_crud(self) -> bool:
        """Test inventory CRUD operations"""
        print("\n📦 Testing Inventory System...")
        
        # Create inventory item
        create_data = {
            "room_type": "bungalov",
            "room_type_name": "Göl Manzaralı Test Bungalov",
            "total_rooms": 10,
            "description": "Test envanter açıklaması",
            "features": ["wifi", "klima", "balkon"],
            "capacity_label": "2+1",
            "pax": 4,
            "image_urls": []
        }
        
        response = self.make_request("POST", "/inventory", create_data)
        if response.status_code == 200:
            inventory_data = response.json()
            inventory_id = inventory_data["id"]
            self.inventory_ids.append(inventory_id)
            self.log_test("Create inventory item", True)
        else:
            self.log_test("Create inventory item", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
        
        # Get inventory list
        response = self.make_request("GET", "/inventory")
        if response.status_code == 200:
            inventory_list = response.json()
            self.log_test("List inventory items", True)
        else:
            self.log_test("List inventory items", False, f"Status: {response.status_code}")
        
        # Get single inventory item
        response = self.make_request("GET", f"/inventory/{inventory_id}")
        if response.status_code == 200:
            self.log_test("Get single inventory item", True)
        else:
            self.log_test("Get single inventory item", False, f"Status: {response.status_code}")
        
        # Update inventory item
        update_data = {
            "room_type_name": "Güncellenmiş Test Bungalov",
            "total_rooms": 12
        }
        response = self.make_request("PUT", f"/inventory/{inventory_id}", update_data)
        if response.status_code == 200:
            self.log_test("Update inventory item", True)
        else:
            self.log_test("Update inventory item", False, f"Status: {response.status_code}")
        
        return True
    
    def test_inventory_availability(self) -> bool:
        """Test inventory availability management"""
        print("\n📅 Testing Inventory Availability...")
        
        if not self.inventory_ids:
            self.log_test("Bulk availability (no inventory)", False, "No inventory items available")
            return False
        
        inventory_id = self.inventory_ids[0]
        
        # Set bulk availability
        today = date.today()
        start_date = today + timedelta(days=30)
        end_date = start_date + timedelta(days=10)
        
        bulk_data = {
            "inventory_id": inventory_id,
            "date_start": start_date.isoformat(),
            "date_end": end_date.isoformat(),
            "available_rooms": 8,
            "price_per_night": 1500.0,
            "notes": "Test availability"
        }
        
        response = self.make_request("POST", "/inventory/availability/bulk", bulk_data)
        if response.status_code == 200:
            result = response.json()
            self.log_test("Bulk availability set", True)
        else:
            self.log_test("Bulk availability set", False, f"Status: {response.status_code}, Response: {response.text}")
        
        # Get calendar view
        month = start_date.strftime("%Y-%m")
        response = self.make_request("GET", f"/inventory/{inventory_id}/calendar", params={"month": month})
        if response.status_code == 200:
            calendar_data = response.json()
            self.log_test("Calendar view", True)
        else:
            self.log_test("Calendar view", False, f"Status: {response.status_code}")
        
        # Check availability
        check_params = {
            "room_type": "bungalov",
            "date_start": start_date.isoformat(),
            "date_end": (start_date + timedelta(days=5)).isoformat()
        }
        response = self.make_request("GET", "/inventory/check-availability", params=check_params)
        if response.status_code == 200:
            availability = response.json()
            self.log_test("Check availability", True)
        else:
            self.log_test("Check availability", False, f"Status: {response.status_code}")
        
        return True
    
    def test_inventory_summary(self) -> bool:
        """Test inventory summary"""
        response = self.make_request("GET", "/inventory/summary/all")
        if response.status_code == 200:
            summary = response.json()
            self.log_test("Inventory summary", True)
            return True
        else:
            self.log_test("Inventory summary", False, f"Status: {response.status_code}")
            return False
    
    def test_pricing_rules_crud(self) -> bool:
        """Test pricing rules CRUD operations"""
        print("\n💰 Testing Pricing Engine...")
        
        # Create seasonal rule
        seasonal_rule = {
            "name": "Yaz Sezonu Test",
            "rule_type": "seasonal",
            "room_type": "bungalov",
            "multiplier": 1.5,
            "date_start": "2026-06-01",
            "date_end": "2026-09-01",
            "is_active": True,
            "priority": 10
        }
        
        response = self.make_request("POST", "/pricing/rules", seasonal_rule)
        if response.status_code == 200:
            rule_data = response.json()
            self.pricing_rule_ids.append(rule_data["id"])
            self.log_test("Create seasonal pricing rule", True)
        else:
            self.log_test("Create seasonal pricing rule", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
        
        # Create weekend rule
        weekend_rule = {
            "name": "Hafta Sonu Test",
            "rule_type": "weekend",
            "multiplier": 1.2,
            "weekend_days": [4, 5, 6],  # Friday, Saturday, Sunday
            "is_active": True,
            "priority": 5
        }
        
        response = self.make_request("POST", "/pricing/rules", weekend_rule)
        if response.status_code == 200:
            rule_data = response.json()
            self.pricing_rule_ids.append(rule_data["id"])
            self.log_test("Create weekend pricing rule", True)
        else:
            self.log_test("Create weekend pricing rule", False, f"Status: {response.status_code}")
        
        # Create early bird rule
        early_bird_rule = {
            "name": "Erken Rezervasyon Test",
            "rule_type": "early_bird",
            "multiplier": 0.9,
            "days_before_min": 30,
            "days_before_max": 90,
            "is_active": True,
            "priority": 3
        }
        
        response = self.make_request("POST", "/pricing/rules", early_bird_rule)
        if response.status_code == 200:
            rule_data = response.json()
            self.pricing_rule_ids.append(rule_data["id"])
            self.log_test("Create early bird pricing rule", True)
        else:
            self.log_test("Create early bird pricing rule", False, f"Status: {response.status_code}")
        
        # List pricing rules
        response = self.make_request("GET", "/pricing/rules")
        if response.status_code == 200:
            rules = response.json()
            self.log_test("List pricing rules", True)
        else:
            self.log_test("List pricing rules", False, f"Status: {response.status_code}")
        
        # Update pricing rule
        if self.pricing_rule_ids:
            rule_id = self.pricing_rule_ids[0]
            update_data = {
                "name": "Güncellenmiş Yaz Sezonu",
                "multiplier": 1.6
            }
            response = self.make_request("PUT", f"/pricing/rules/{rule_id}", update_data)
            if response.status_code == 200:
                self.log_test("Update pricing rule", True)
            else:
                self.log_test("Update pricing rule", False, f"Status: {response.status_code}")
        
        return True
    
    def test_dynamic_pricing(self) -> bool:
        """Test dynamic price calculation"""
        today = date.today()
        start_date = today + timedelta(days=45)  # Should hit early bird rule
        end_date = start_date + timedelta(days=7)  # Include weekend days
        
        calculate_data = {
            "room_type": "bungalov",
            "date_start": start_date.isoformat(),
            "date_end": end_date.isoformat(),
            "base_price": 1000.0
        }
        
        response = self.make_request("POST", "/pricing/calculate", calculate_data)
        if response.status_code == 200:
            result = response.json()
            self.log_test("Dynamic price calculation", True)
            print(f"   Base price: {result.get('base_price')}, Final price: {result.get('total_price')}")
            return True
        else:
            self.log_test("Dynamic price calculation", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
    
    def test_market_comparison(self) -> bool:
        """Test market comparison"""
        response = self.make_request("GET", "/pricing/market-comparison", params={"room_type": "bungalov"})
        if response.status_code == 200:
            comparison = response.json()
            self.log_test("Market comparison", True)
            return True
        else:
            self.log_test("Market comparison", False, f"Status: {response.status_code}")
            return False
    
    def test_price_history(self) -> bool:
        """Test price history"""
        response = self.make_request("GET", "/pricing/history", params={"room_type": "bungalov", "months": 3})
        if response.status_code == 200:
            history = response.json()
            self.log_test("Price history", True)
            return True
        else:
            self.log_test("Price history", False, f"Status: {response.status_code}")
            return False
    
    def test_performance_health(self) -> bool:
        """Test performance health check (no auth required)"""
        print("\n⚡ Testing Performance System...")
        
        response = self.make_request("GET", "/performance/health", auth=False)
        if response.status_code == 200:
            health = response.json()
            self.log_test("Performance health check", True)
            print(f"   Status: {health.get('status')}, Response time: {health.get('total_response_ms')}ms")
            return True
        else:
            self.log_test("Performance health check", False, f"Status: {response.status_code}")
            return False
    
    def test_performance_benchmark(self) -> bool:
        """Test performance benchmark (auth required)"""
        response = self.make_request("GET", "/performance/benchmark")
        if response.status_code == 200:
            benchmark = response.json()
            self.log_test("Performance benchmark", True)
            print(f"   Grade: {benchmark.get('grade')}, Total: {benchmark.get('total_ms')}ms")
            return True
        else:
            self.log_test("Performance benchmark", False, f"Status: {response.status_code}")
            return False
    
    def test_db_indexes(self) -> bool:
        """Test DB indexes listing (admin required)"""
        response = self.make_request("GET", "/performance/db-indexes")
        if response.status_code == 200:
            indexes = response.json()
            self.log_test("DB indexes list", True)
            print(f"   Collections with indexes: {len(indexes)}")
            return True
        else:
            self.log_test("DB indexes list", False, f"Status: {response.status_code}")
            return False
    
    def test_overbooking_prevention(self) -> bool:
        """Test overbooking prevention scenario"""
        print("\n🚫 Testing Overbooking Prevention...")
        
        if not self.inventory_ids:
            self.log_test("Overbooking prevention", False, "No inventory available for testing")
            return False
        
        inventory_id = self.inventory_ids[0]
        
        # Set availability to only 2 rooms for tomorrow
        tomorrow = date.today() + timedelta(days=1)
        
        bulk_data = {
            "inventory_id": inventory_id,
            "date_start": tomorrow.isoformat(),
            "date_end": tomorrow.isoformat(),
            "available_rooms": 2,
            "price_per_night": 1000.0
        }
        
        response = self.make_request("POST", "/inventory/availability/bulk", bulk_data)
        if response.status_code != 200:
            self.log_test("Overbooking prevention setup", False, f"Failed to set limited availability")
            return False
        
        # Check availability - should show limited rooms
        check_params = {
            "room_type": "bungalov",
            "date_start": tomorrow.isoformat(),
            "date_end": tomorrow.isoformat()
        }
        response = self.make_request("POST", "/inventory/check-availability", params=check_params)
        if response.status_code == 200:
            availability = response.json()
            if availability.get("min_available") == 2:
                self.log_test("Overbooking prevention", True)
                return True
            else:
                self.log_test("Overbooking prevention", False, f"Expected 2 available rooms, got {availability.get('min_available')}")
                return False
        else:
            self.log_test("Overbooking prevention", False, f"Availability check failed")
            return False
    
    def cleanup(self) -> None:
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete pricing rules
        for rule_id in self.pricing_rule_ids:
            response = self.make_request("DELETE", f"/pricing/rules/{rule_id}")
            if response.status_code == 200:
                print(f"   Deleted pricing rule: {rule_id}")
        
        # Delete inventory items (this also deletes related availability data)
        for inv_id in self.inventory_ids:
            response = self.make_request("DELETE", f"/inventory/{inv_id}")
            if response.status_code == 200:
                print(f"   Deleted inventory item: {inv_id}")
    
    def run_all_tests(self) -> bool:
        """Run all tests and return overall success"""
        print("🚀 Starting CapX Backend Testing Suite...")
        print(f"Testing against: {BASE_URL}")
        
        # Login first
        if not self.login():
            return False
        
        try:
            # Test all systems
            self.test_inventory_crud()
            self.test_inventory_availability()
            self.test_inventory_summary()
            self.test_pricing_rules_crud()
            self.test_dynamic_pricing()
            self.test_market_comparison()
            self.test_price_history()
            self.test_performance_health()
            self.test_performance_benchmark()
            self.test_db_indexes()
            self.test_overbooking_prevention()
            
        finally:
            # Always cleanup
            self.cleanup()
        
        # Summary
        print(f"\n📊 Test Results Summary:")
        print(f"✅ Passed: {len(self.passed_tests)}")
        print(f"❌ Failed: {len(self.failed_tests)}")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for test_name, error in self.failed_tests:
                print(f"   • {test_name}: {error}")
        
        return len(self.failed_tests) == 0

def main():
    tester = CapXTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()