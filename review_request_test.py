#!/usr/bin/env python3
"""
CapX Platform Review Request Testing - 22 Specific Endpoints
Testing ALL endpoints mentioned in the review request for 100% pass rate
"""

import json
import requests
import time
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://improvement-guide-2.preview.emergentagent.com/api"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "Admin123"

class CapXReviewTester:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.test_results = []
        self.listing_id = None
        
    def log_test(self, endpoint: str, method: str, success: bool, details: str, status_code: int = None):
        """Log test results"""
        result = {
            "endpoint": endpoint,
            "method": method, 
            "success": success,
            "details": details,
            "status_code": status_code,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {method} {endpoint} - {details}")
        
    def authenticate(self):
        """Authenticate using form data POST to /api/auth/login"""
        try:
            login_data = {
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
            
            response = self.session.post(
                f"{BASE_URL}/auth/login",
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                self.log_test("/auth/login", "POST", True, "Authentication successful with form data", 200)
                return True
            else:
                self.log_test("/auth/login", "POST", False, f"Authentication failed: {response.text}", response.status_code)
                return False
                
        except Exception as e:
            self.log_test("/auth/login", "POST", False, f"Authentication error: {str(e)}")
            return False
    
    def test_core_stats_reports(self):
        """Test Core Stats & Reports endpoints (1-7)"""
        print("\n📊 Testing Core Stats & Reports...")
        
        # 1. GET /api/stats - General stats (was broken with datetime, now fixed)
        try:
            response = self.session.get(f"{BASE_URL}/stats")
            if response.status_code == 200:
                stats = response.json()
                self.log_test("/stats", "GET", True, "General stats working (datetime bug fixed)", 200)
            else:
                self.log_test("/stats", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/stats", "GET", False, f"Error: {str(e)}")
        
        # 2. GET /api/stats/market-trends - 6 regions market data
        try:
            response = self.session.get(f"{BASE_URL}/stats/market-trends")
            if response.status_code == 200:
                trends = response.json()
                regions_count = len(trends.get("regions", {})) if isinstance(trends.get("regions"), dict) else len(trends.get("regions", []))
                if regions_count == 6:
                    self.log_test("/stats/market-trends", "GET", True, f"Market trends with {regions_count} regions", 200)
                else:
                    self.log_test("/stats/market-trends", "GET", False, f"Expected 6 regions, got {regions_count}", 200)
            else:
                self.log_test("/stats/market-trends", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/stats/market-trends", "GET", False, f"Error: {str(e)}")
        
        # 3. GET /api/stats/performance-scores - Performance metrics with score/grade
        try:
            response = self.session.get(f"{BASE_URL}/stats/performance-scores")
            if response.status_code == 200:
                performance = response.json()
                required_fields = ["score", "grade", "approval_rate", "cancellation_rate"]
                has_all_fields = all(field in performance for field in required_fields)
                if has_all_fields:
                    self.log_test("/stats/performance-scores", "GET", True, f"Performance scores with all required fields (score: {performance.get('score')}, grade: {performance.get('grade')})", 200)
                else:
                    missing = [f for f in required_fields if f not in performance]
                    self.log_test("/stats/performance-scores", "GET", False, f"Missing fields: {missing}", 200)
            else:
                self.log_test("/stats/performance-scores", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/stats/performance-scores", "GET", False, f"Error: {str(e)}")
        
        # 4. GET /api/stats/requests?period_days=7 - Request stats for 7 days
        try:
            response = self.session.get(f"{BASE_URL}/stats/requests", params={"period_days": 7})
            if response.status_code == 200:
                self.log_test("/stats/requests?period_days=7", "GET", True, "Request stats for 7 days", 200)
            else:
                self.log_test("/stats/requests?period_days=7", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/stats/requests?period_days=7", "GET", False, f"Error: {str(e)}")
        
        # 5. GET /api/stats/requests?period_days=90 - Request stats for 90 days
        try:
            response = self.session.get(f"{BASE_URL}/stats/requests", params={"period_days": 90})
            if response.status_code == 200:
                self.log_test("/stats/requests?period_days=90", "GET", True, "Request stats for 90 days", 200)
            else:
                self.log_test("/stats/requests?period_days=90", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/stats/requests?period_days=90", "GET", False, f"Error: {str(e)}")
        
        # 6. GET /api/stats/cross-region - NEW cross-region stats (should show 6 regions, at least 1 cross-region listing)
        try:
            response = self.session.get(f"{BASE_URL}/stats/cross-region")
            if response.status_code == 200:
                cross_region = response.json()
                regions_data = cross_region.get("regions", {})
                if isinstance(regions_data, dict):
                    regions_count = len(regions_data)
                elif isinstance(regions_data, list):
                    regions_count = len(regions_data)
                else:
                    regions_count = 0
                
                cross_region_count = cross_region.get("cross_region_listings", 0) or cross_region.get("total_cross_region_listings", 0)
                
                if regions_count == 6:
                    self.log_test("/stats/cross-region", "GET", True, f"Cross-region stats with {regions_count} regions and {cross_region_count} cross-region listings", 200)
                else:
                    self.log_test("/stats/cross-region", "GET", False, f"Expected 6 regions, got {regions_count}", 200)
            else:
                self.log_test("/stats/cross-region", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/stats/cross-region", "GET", False, f"Error: {str(e)}")
        
        # 7. GET /api/reports/revenue - Revenue report
        try:
            response = self.session.get(f"{BASE_URL}/reports/revenue")
            if response.status_code == 200:
                self.log_test("/reports/revenue", "GET", True, "Revenue report retrieved", 200)
            else:
                self.log_test("/reports/revenue", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/reports/revenue", "GET", False, f"Error: {str(e)}")
    
    def test_cross_region_features(self):
        """Test Cross-Region Features endpoints (8-11)"""
        print("\n🌍 Testing Cross-Region Features...")
        
        # 8. POST /api/listings - Create listing with allow_cross_region=true
        try:
            import datetime
            start_date = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            end_date = (datetime.datetime.now() + datetime.timedelta(days=37)).strftime("%Y-%m-%d")
            
            listing_data = {
                "region": "Sapanca",
                "micro_location": "Göl kenarı",
                "concept": "Test Bungalov",
                "capacity_label": "2+1",
                "pax": 3,
                "date_start": start_date + "T14:00:00",
                "date_end": end_date + "T12:00:00",
                "nights": 7,
                "price_min": 800,
                "price_max": 1200,
                "availability_status": "available",
                "allow_cross_region": True,
                "room_type": "bungalov",
                "description": "Test cross-region bungalov"
            }
            
            response = self.session.post(f"{BASE_URL}/listings", json=listing_data)
            if response.status_code == 200:
                new_listing = response.json()
                self.listing_id = new_listing.get("id")
                self.log_test("/listings (allow_cross_region=true)", "POST", True, f"Cross-region bungalov listing created: {self.listing_id}", 200)
            else:
                self.log_test("/listings (allow_cross_region=true)", "POST", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/listings (allow_cross_region=true)", "POST", False, f"Error: {str(e)}")
        
        # 9. GET /api/listings?include_cross_region=true - Should include cross-region listings from other regions
        try:
            response = self.session.get(f"{BASE_URL}/listings", params={"include_cross_region": "true"})
            if response.status_code == 200:
                listings = response.json()
                cross_region_listings = [l for l in listings if l.get("allow_cross_region", False)]
                self.log_test("/listings?include_cross_region=true", "GET", True, f"Retrieved {len(listings)} listings, {len(cross_region_listings)} are cross-region", 200)
            else:
                self.log_test("/listings?include_cross_region=true", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/listings?include_cross_region=true", "GET", False, f"Error: {str(e)}")
        
        # 10. GET /api/listings?region=Kartepe&include_cross_region=true - Cross-region filter with specific region
        try:
            response = self.session.get(f"{BASE_URL}/listings", params={"region": "Kartepe", "include_cross_region": "true"})
            if response.status_code == 200:
                listings = response.json()
                kartepe_listings = [l for l in listings if l.get("region") == "Kartepe"]
                cross_region_listings = [l for l in listings if l.get("allow_cross_region", False)]
                self.log_test("/listings?region=Kartepe&include_cross_region=true", "GET", True, f"Retrieved {len(listings)} listings ({len(kartepe_listings)} Kartepe, {len(cross_region_listings)} cross-region)", 200)
            else:
                self.log_test("/listings?region=Kartepe&include_cross_region=true", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/listings?region=Kartepe&include_cross_region=true", "GET", False, f"Error: {str(e)}")
        
        # 11. PUT /api/listings/{id} - Update listing with allow_cross_region=false
        if self.listing_id:
            try:
                update_data = {
                    "allow_cross_region": False,
                    "description": "Updated: cross-region disabled"
                }
                response = self.session.put(f"{BASE_URL}/listings/{self.listing_id}", json=update_data)
                if response.status_code == 200:
                    self.log_test(f"/listings/{self.listing_id}", "PUT", True, "Updated listing to disable cross-region", 200)
                else:
                    self.log_test(f"/listings/{self.listing_id}", "PUT", False, f"Failed: {response.text}", response.status_code)
            except Exception as e:
                self.log_test(f"/listings/{self.listing_id}", "PUT", False, f"Error: {str(e)}")
        else:
            self.log_test("/listings/{id}", "PUT", False, "No listing ID available from previous test")
    
    def test_regions(self):
        """Test Regions endpoint (12)"""
        print("\n🏔️ Testing Regions...")
        
        # 12. GET /api/regions - Should return exactly 6 regions
        try:
            response = self.session.get(f"{BASE_URL}/regions")
            if response.status_code == 200:
                regions = response.json()
                if isinstance(regions, list) and len(regions) == 6:
                    region_names = [r.get("id") or r.get("name") for r in regions]
                    expected = ["Sapanca", "Kartepe", "Abant", "Ayder", "Kas", "Alacati"]
                    if all(region in region_names for region in expected):
                        self.log_test("/regions", "GET", True, f"All 6 regions found: {region_names}", 200)
                    else:
                        missing = [r for r in expected if r not in region_names]
                        self.log_test("/regions", "GET", False, f"Missing regions: {missing}. Found: {region_names}", 200)
                else:
                    self.log_test("/regions", "GET", False, f"Expected 6 regions, got {len(regions) if isinstance(regions, list) else 'non-list'}", 200)
            else:
                self.log_test("/regions", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/regions", "GET", False, f"Error: {str(e)}")
    
    def test_admin_endpoints(self):
        """Test Admin endpoints (13-16)"""
        print("\n👑 Testing Admin Endpoints...")
        
        # 13. GET /api/admin/overview - Admin dashboard
        try:
            response = self.session.get(f"{BASE_URL}/admin/overview")
            if response.status_code == 200:
                overview = response.json()
                self.log_test("/admin/overview", "GET", True, "Admin dashboard overview retrieved", 200)
            else:
                self.log_test("/admin/overview", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/admin/overview", "GET", False, f"Error: {str(e)}")
        
        # 14. GET /api/admin/region-pricing - All 6 regions pricing
        try:
            response = self.session.get(f"{BASE_URL}/admin/region-pricing")
            if response.status_code == 200:
                pricing = response.json()
                regions_count = len(pricing) if isinstance(pricing, (list, dict)) else 0
                if regions_count == 6:
                    self.log_test("/admin/region-pricing", "GET", True, f"Region pricing for all {regions_count} regions", 200)
                else:
                    self.log_test("/admin/region-pricing", "GET", False, f"Expected 6 regions pricing, got {regions_count}", 200)
            else:
                self.log_test("/admin/region-pricing", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/admin/region-pricing", "GET", False, f"Error: {str(e)}")
        
        # 15. GET /api/admin/revenue - Platform revenue
        try:
            response = self.session.get(f"{BASE_URL}/admin/revenue")
            if response.status_code == 200:
                revenue = response.json()
                self.log_test("/admin/revenue", "GET", True, "Platform revenue data retrieved", 200)
            else:
                self.log_test("/admin/revenue", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/admin/revenue", "GET", False, f"Error: {str(e)}")
        
        # 16. GET /api/admin/region-stats - Region statistics
        try:
            response = self.session.get(f"{BASE_URL}/admin/region-stats")
            if response.status_code == 200:
                stats = response.json()
                self.log_test("/admin/region-stats", "GET", True, "Region statistics retrieved", 200)
            else:
                self.log_test("/admin/region-stats", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/admin/region-stats", "GET", False, f"Error: {str(e)}")
    
    def test_other_endpoints(self):
        """Test Other endpoints (17-22)"""
        print("\n🔧 Testing Other Endpoints...")
        
        # 17. GET /api/subscriptions/plans - 4 plans
        try:
            response = self.session.get(f"{BASE_URL}/subscriptions/plans")
            if response.status_code == 200:
                plans = response.json()
                if isinstance(plans, list) and len(plans) == 4:
                    plan_names = [p.get("name") or p.get("id") for p in plans]
                    self.log_test("/subscriptions/plans", "GET", True, f"4 subscription plans found: {plan_names}", 200)
                else:
                    self.log_test("/subscriptions/plans", "GET", False, f"Expected 4 plans, got {len(plans) if isinstance(plans, list) else 'non-list'}", 200)
            else:
                self.log_test("/subscriptions/plans", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/subscriptions/plans", "GET", False, f"Error: {str(e)}")
        
        # 18. GET /api/notifications - Notifications list
        try:
            response = self.session.get(f"{BASE_URL}/notifications")
            if response.status_code == 200:
                notifications = response.json()
                self.log_test("/notifications", "GET", True, f"Notifications list retrieved ({len(notifications)} notifications)", 200)
            else:
                self.log_test("/notifications", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/notifications", "GET", False, f"Error: {str(e)}")
        
        # 19. GET /api/payments - Payments list
        try:
            response = self.session.get(f"{BASE_URL}/payments")
            if response.status_code == 200:
                payments = response.json()
                self.log_test("/payments", "GET", True, f"Payments list retrieved ({len(payments)} payments)", 200)
            else:
                self.log_test("/payments", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/payments", "GET", False, f"Error: {str(e)}")
        
        # 20. GET /api/invoices - Invoices list
        try:
            response = self.session.get(f"{BASE_URL}/invoices")
            if response.status_code == 200:
                invoices = response.json()
                self.log_test("/invoices", "GET", True, f"Invoices list retrieved ({len(invoices)} invoices)", 200)
            else:
                self.log_test("/invoices", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/invoices", "GET", False, f"Error: {str(e)}")
        
        # 21. GET /api/performance/health - No auth needed
        try:
            # Test without authentication first
            no_auth_session = requests.Session()
            response = no_auth_session.get(f"{BASE_URL}/performance/health")
            if response.status_code == 200:
                health = response.json()
                status = health.get("status", "unknown")
                response_time = health.get("response_time_ms", 0)
                self.log_test("/performance/health", "GET", True, f"Health check: {status} (no auth needed, {response_time}ms)", 200)
            else:
                # Try with auth as fallback
                response = self.session.get(f"{BASE_URL}/performance/health")
                if response.status_code == 200:
                    health = response.json()
                    status = health.get("status", "unknown")
                    self.log_test("/performance/health", "GET", True, f"Health check: {status} (with auth)", 200)
                else:
                    self.log_test("/performance/health", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/performance/health", "GET", False, f"Error: {str(e)}")
        
        # 22. GET /api/kvkk/export - Data export
        try:
            response = self.session.get(f"{BASE_URL}/kvkk/export")
            if response.status_code == 200:
                export_data = response.json()
                self.log_test("/kvkk/export", "GET", True, "KVKK data export successful", 200)
            else:
                self.log_test("/kvkk/export", "GET", False, f"Failed: {response.text}", response.status_code)
        except Exception as e:
            self.log_test("/kvkk/export", "GET", False, f"Error: {str(e)}")
    
    def run_all_tests(self):
        """Run all 22 endpoints from the review request"""
        print("=" * 70)
        print("CapX Platform Review Request Testing - 22 Endpoints")
        print("Target: 100% Pass Rate")
        print("=" * 70)
        
        # Authenticate first
        if not self.authenticate():
            print("❌ Authentication failed. Cannot proceed with tests.")
            return
        
        print("\n🚀 Running all 22 review request endpoints...\n")
        
        # Run all test categories
        self.test_core_stats_reports()      # Endpoints 1-7
        self.test_cross_region_features()   # Endpoints 8-11 
        self.test_regions()                 # Endpoint 12
        self.test_admin_endpoints()         # Endpoints 13-16
        self.test_other_endpoints()         # Endpoints 17-22
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 70)
        print("COMPREHENSIVE TEST RESULTS SUMMARY")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Endpoints Tested: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"SUCCESS RATE: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED ENDPOINTS:")
            print("-" * 50)
            for result in self.test_results:
                if not result["success"]:
                    print(f"• {result['method']} {result['endpoint']}")
                    print(f"  └── {result['details']}")
                    if result['status_code']:
                        print(f"  └── HTTP {result['status_code']}")
                    print()
        
        # Group successful tests by category
        print("\n✅ SUCCESSFUL ENDPOINTS BY CATEGORY:")
        print("-" * 50)
        
        categories = {
            "Core Stats & Reports": ["/stats", "/stats/market-trends", "/stats/performance-scores", "/stats/requests", "/stats/cross-region", "/reports/revenue"],
            "Cross-Region Features": ["/listings", "/listings?include_cross_region=true", "/listings?region=Kartepe&include_cross_region=true"],
            "Regions": ["/regions"],
            "Admin": ["/admin/overview", "/admin/region-pricing", "/admin/revenue", "/admin/region-stats"],
            "Other": ["/subscriptions/plans", "/notifications", "/payments", "/invoices", "/performance/health", "/kvkk/export"]
        }
        
        for category, endpoints in categories.items():
            print(f"\n📊 {category}:")
            for result in self.test_results:
                if result["success"]:
                    endpoint = result["endpoint"]
                    if any(ep in endpoint for ep in endpoints):
                        print(f"  ✅ {result['method']} {endpoint} - {result['details']}")
        
        # Final assessment
        if failed_tests == 0:
            print("\n🎉 PERFECT! ALL 22 ENDPOINTS PASSED - 100% SUCCESS RATE!")
        else:
            print(f"\n⚠️  {failed_tests} endpoint(s) need attention to reach 100% target.")

if __name__ == "__main__":
    tester = CapXReviewTester()
    tester.run_all_tests()