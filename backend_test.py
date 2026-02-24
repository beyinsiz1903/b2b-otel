#!/usr/bin/env python3
"""
CapX Hotel Platform v4 Backend API Testing Script
Tests all new endpoints for the v4 update
"""

import json
import requests
import time
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://improvement-guide-2.preview.emergentagent.com/api"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "Admin123"

class CapXAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.test_results = []
        
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
        """Authenticate and get access token"""
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
                self.log_test("/auth/login", "POST", True, "Authentication successful", 200)
                return True
            else:
                self.log_test("/auth/login", "POST", False, f"Authentication failed: {response.text}", response.status_code)
                return False
                
        except Exception as e:
            self.log_test("/auth/login", "POST", False, f"Authentication error: {str(e)}")
            return False
    
    def test_regions(self):
        """Test GET /api/regions - Should return 6 regions"""
        try:
            response = self.session.get(f"{BASE_URL}/regions")
            
            if response.status_code == 200:
                regions = response.json()
                if isinstance(regions, list) and len(regions) == 6:
                    region_names = [r.get("id") for r in regions]
                    expected_regions = ["Sapanca", "Kartepe", "Abant", "Ayder", "Kas", "Alacati"]
                    if all(region in region_names for region in expected_regions):
                        self.log_test("/regions", "GET", True, f"Found all 6 regions: {region_names}", 200)
                    else:
                        self.log_test("/regions", "GET", False, f"Missing expected regions. Found: {region_names}", 200)
                else:
                    self.log_test("/regions", "GET", False, f"Expected 6 regions, got {len(regions) if isinstance(regions, list) else 'non-list'}", 200)
            else:
                self.log_test("/regions", "GET", False, f"Request failed: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/regions", "GET", False, f"Error: {str(e)}")
    
    def test_enhanced_filters(self):
        """Test GET /api/listings with new filter parameters"""
        try:
            # Test basic filters
            params = {
                "date_from": "2025-02-01",
                "date_to": "2025-02-10",
                "price_min": "500",
                "pax_max": "4",
                "room_type": "bungalov",
                "features": "wifi,klima"
            }
            
            response = self.session.get(f"{BASE_URL}/listings", params=params)
            
            if response.status_code == 200:
                listings = response.json()
                self.log_test("/listings", "GET", True, f"Enhanced filters working - returned {len(listings)} listings", 200)
                
                # Test another set of filters
                params2 = {
                    "region": "Sapanca",
                    "pax_min": "2",
                    "price_max": "2000",
                    "breakfast_included": "true"
                }
                
                response2 = self.session.get(f"{BASE_URL}/listings", params=params2)
                if response2.status_code == 200:
                    listings2 = response2.json()
                    self.log_test("/listings (filter set 2)", "GET", True, f"Secondary filter test passed - returned {len(listings2)} listings", 200)
                else:
                    self.log_test("/listings (filter set 2)", "GET", False, f"Secondary filter test failed: {response2.text}", response2.status_code)
            else:
                self.log_test("/listings", "GET", False, f"Enhanced filters failed: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/listings", "GET", False, f"Error: {str(e)}")
    
    def test_payment_system(self):
        """Test the mock payment system"""
        # First, get matches to find one to test with
        try:
            response = self.session.get(f"{BASE_URL}/matches")
            
            if response.status_code == 200:
                matches = response.json()
                self.log_test("/matches", "GET", True, f"Retrieved {len(matches)} matches", 200)
                
                if matches:
                    # Use the first match for payment testing
                    match_id = matches[0].get("id") or matches[0].get("_id")
                    
                    # Test payment initiation
                    payment_data = {
                        "match_id": match_id,
                        "method": "credit_card"
                    }
                    
                    payment_response = self.session.post(f"{BASE_URL}/payments/initiate", json=payment_data)
                    
                    if payment_response.status_code == 200:
                        payment_info = payment_response.json()
                        payment_id = payment_info.get("payment_id")
                        self.log_test("/payments/initiate", "POST", True, f"Payment initiated: {payment_id}", 200)
                        
                        # Test payment list
                        payments_response = self.session.get(f"{BASE_URL}/payments")
                        if payments_response.status_code == 200:
                            payments = payments_response.json()
                            self.log_test("/payments", "GET", True, f"Retrieved {len(payments)} payments", 200)
                        else:
                            self.log_test("/payments", "GET", False, f"Failed to list payments: {payments_response.text}", payments_response.status_code)
                        
                        # Test payment completion
                        if payment_id:
                            complete_response = self.session.post(f"{BASE_URL}/payments/{payment_id}/complete")
                            if complete_response.status_code == 200:
                                self.log_test(f"/payments/{payment_id}/complete", "POST", True, "Payment completed successfully", 200)
                            else:
                                self.log_test(f"/payments/{payment_id}/complete", "POST", False, f"Payment completion failed: {complete_response.text}", complete_response.status_code)
                    else:
                        self.log_test("/payments/initiate", "POST", False, f"Payment initiation failed: {payment_response.text}", payment_response.status_code)
                else:
                    self.log_test("/matches", "GET", False, "No matches found to test payment with", 200)
            else:
                self.log_test("/matches", "GET", False, f"Failed to retrieve matches: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/payments/*", "MIXED", False, f"Payment system error: {str(e)}")
    
    def test_invoice_system(self):
        """Test GET /api/invoices"""
        try:
            response = self.session.get(f"{BASE_URL}/invoices")
            
            if response.status_code == 200:
                invoices = response.json()
                self.log_test("/invoices", "GET", True, f"Retrieved {len(invoices)} invoices", 200)
            else:
                self.log_test("/invoices", "GET", False, f"Failed to retrieve invoices: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/invoices", "GET", False, f"Error: {str(e)}")
    
    def test_subscription_system(self):
        """Test subscription system endpoints"""
        try:
            # Test subscription plans
            plans_response = self.session.get(f"{BASE_URL}/subscriptions/plans")
            
            if plans_response.status_code == 200:
                plans = plans_response.json()
                if isinstance(plans, list) and len(plans) == 4:
                    self.log_test("/subscriptions/plans", "GET", True, f"Found 4 subscription plans", 200)
                    
                    # Test subscription
                    subscribe_data = {
                        "plan_id": "basic",
                        "billing_cycle": "monthly"
                    }
                    
                    subscribe_response = self.session.post(f"{BASE_URL}/subscriptions/subscribe", json=subscribe_data)
                    
                    if subscribe_response.status_code == 200:
                        self.log_test("/subscriptions/subscribe", "POST", True, "Subscription created successfully", 200)
                        
                        # Test my subscription
                        my_sub_response = self.session.get(f"{BASE_URL}/subscriptions/my")
                        if my_sub_response.status_code == 200:
                            subscription = my_sub_response.json()
                            self.log_test("/subscriptions/my", "GET", True, f"Retrieved active subscription: {subscription.get('plan_id', 'unknown')}", 200)
                            
                            # Test subscription cancellation
                            cancel_response = self.session.post(f"{BASE_URL}/subscriptions/cancel")
                            if cancel_response.status_code == 200:
                                self.log_test("/subscriptions/cancel", "POST", True, "Subscription cancelled successfully", 200)
                            else:
                                self.log_test("/subscriptions/cancel", "POST", False, f"Cancellation failed: {cancel_response.text}", cancel_response.status_code)
                        else:
                            self.log_test("/subscriptions/my", "GET", False, f"Failed to get subscription: {my_sub_response.text}", my_sub_response.status_code)
                    else:
                        self.log_test("/subscriptions/subscribe", "POST", False, f"Subscription failed: {subscribe_response.text}", subscribe_response.status_code)
                else:
                    self.log_test("/subscriptions/plans", "GET", False, f"Expected 4 plans, got {len(plans) if isinstance(plans, list) else 'non-list'}", 200)
            else:
                self.log_test("/subscriptions/plans", "GET", False, f"Failed to get plans: {plans_response.text}", plans_response.status_code)
                
        except Exception as e:
            self.log_test("/subscriptions/*", "MIXED", False, f"Subscription system error: {str(e)}")
    
    def test_notification_system(self):
        """Test notification system endpoints"""
        try:
            # Test notifications list
            notifications_response = self.session.get(f"{BASE_URL}/notifications")
            
            if notifications_response.status_code == 200:
                notifications = notifications_response.json()
                self.log_test("/notifications", "GET", True, f"Retrieved {len(notifications)} notifications", 200)
                
                # Test unread count
                unread_response = self.session.get(f"{BASE_URL}/notifications/unread-count")
                if unread_response.status_code == 200:
                    unread_data = unread_response.json()
                    unread_count = unread_data.get("count", 0)
                    self.log_test("/notifications/unread-count", "GET", True, f"Unread count: {unread_count}", 200)
                    
                    # Test mark all as read
                    mark_read_response = self.session.put(f"{BASE_URL}/notifications/read-all")
                    if mark_read_response.status_code == 200:
                        self.log_test("/notifications/read-all", "PUT", True, "All notifications marked as read", 200)
                    else:
                        self.log_test("/notifications/read-all", "PUT", False, f"Mark read failed: {mark_read_response.text}", mark_read_response.status_code)
                else:
                    self.log_test("/notifications/unread-count", "GET", False, f"Unread count failed: {unread_response.text}", unread_response.status_code)
            else:
                self.log_test("/notifications", "GET", False, f"Notifications list failed: {notifications_response.text}", notifications_response.status_code)
                
        except Exception as e:
            self.log_test("/notifications/*", "MIXED", False, f"Notification system error: {str(e)}")
    
    def test_revenue_reports(self):
        """Test GET /api/reports/revenue"""
        try:
            response = self.session.get(f"{BASE_URL}/reports/revenue")
            
            if response.status_code == 200:
                revenue_data = response.json()
                self.log_test("/reports/revenue", "GET", True, "Revenue report retrieved successfully", 200)
            else:
                self.log_test("/reports/revenue", "GET", False, f"Revenue report failed: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/reports/revenue", "GET", False, f"Error: {str(e)}")
    
    def test_market_trends(self):
        """Test GET /api/stats/market-trends"""
        try:
            response = self.session.get(f"{BASE_URL}/stats/market-trends")
            
            if response.status_code == 200:
                trends_data = response.json()
                self.log_test("/stats/market-trends", "GET", True, "Market trends retrieved successfully", 200)
            else:
                self.log_test("/stats/market-trends", "GET", False, f"Market trends failed: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/stats/market-trends", "GET", False, f"Error: {str(e)}")
    
    def test_performance_scores(self):
        """Test GET /api/stats/performance-scores"""
        try:
            response = self.session.get(f"{BASE_URL}/stats/performance-scores")
            
            if response.status_code == 200:
                performance_data = response.json()
                self.log_test("/stats/performance-scores", "GET", True, "Performance scores retrieved successfully", 200)
            else:
                self.log_test("/stats/performance-scores", "GET", False, f"Performance scores failed: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/stats/performance-scores", "GET", False, f"Error: {str(e)}")
    
    def test_request_statistics(self):
        """Test GET /api/stats/requests with period parameters"""
        try:
            # Test default request statistics
            response = self.session.get(f"{BASE_URL}/stats/requests")
            
            if response.status_code == 200:
                stats_data = response.json()
                self.log_test("/stats/requests", "GET", True, "Request statistics retrieved successfully", 200)
            else:
                self.log_test("/stats/requests", "GET", False, f"Request statistics failed: {response.text}", response.status_code)
                
            # Test with period_days=7
            response_7 = self.session.get(f"{BASE_URL}/stats/requests", params={"period_days": 7})
            
            if response_7.status_code == 200:
                stats_data_7 = response_7.json()
                self.log_test("/stats/requests?period_days=7", "GET", True, "Request statistics (7 days) retrieved successfully", 200)
            else:
                self.log_test("/stats/requests?period_days=7", "GET", False, f"Request statistics (7 days) failed: {response_7.text}", response_7.status_code)
                
            # Test with period_days=90  
            response_90 = self.session.get(f"{BASE_URL}/stats/requests", params={"period_days": 90})
            
            if response_90.status_code == 200:
                stats_data_90 = response_90.json()
                self.log_test("/stats/requests?period_days=90", "GET", True, "Request statistics (90 days) retrieved successfully", 200)
            else:
                self.log_test("/stats/requests?period_days=90", "GET", False, f"Request statistics (90 days) failed: {response_90.text}", response_90.status_code)
                
        except Exception as e:
            self.log_test("/stats/requests", "GET", False, f"Error: {str(e)}")
    
    def test_kvkk_compliance(self):
        """Test KVKK compliance endpoints"""
        try:
            # Test data export
            export_response = self.session.get(f"{BASE_URL}/kvkk/export")
            
            if export_response.status_code == 200:
                export_data = export_response.json()
                self.log_test("/kvkk/export", "GET", True, "KVKK data export successful", 200)
                
                # Test deletion request
                delete_response = self.session.post(f"{BASE_URL}/kvkk/delete-request")
                if delete_response.status_code == 200:
                    delete_data = delete_response.json()
                    self.log_test("/kvkk/delete-request", "POST", True, "KVKK deletion request created", 200)
                else:
                    self.log_test("/kvkk/delete-request", "POST", False, f"Deletion request failed: {delete_response.text}", delete_response.status_code)
            else:
                self.log_test("/kvkk/export", "GET", False, f"Data export failed: {export_response.text}", export_response.status_code)
                
        except Exception as e:
            self.log_test("/kvkk/*", "MIXED", False, f"KVKK compliance error: {str(e)}")
    
    def test_general_stats(self):
        """Test GET /api/stats - Should return stats without datetime errors"""
        try:
            response = self.session.get(f"{BASE_URL}/stats")
            
            if response.status_code == 200:
                stats_data = response.json()
                self.log_test("/stats", "GET", True, "General stats retrieved successfully (no datetime errors)", 200)
            else:
                self.log_test("/stats", "GET", False, f"General stats failed: {response.text}", response.status_code)
                
        except Exception as e:
            self.log_test("/stats", "GET", False, f"Error: {str(e)}")
    
    def test_cross_region_functionality(self):
        """Test cross-region matching functionality"""
        try:
            # Test GET /api/stats/cross-region
            response = self.session.get(f"{BASE_URL}/stats/cross-region")
            
            if response.status_code == 200:
                cross_region_data = response.json()
                # Check if it returns regions list
                if "regions" in cross_region_data:
                    self.log_test("/stats/cross-region", "GET", True, f"Cross-region stats retrieved with {len(cross_region_data.get('regions', []))} regions", 200)
                else:
                    self.log_test("/stats/cross-region", "GET", True, "Cross-region stats retrieved successfully", 200)
            else:
                self.log_test("/stats/cross-region", "GET", False, f"Cross-region stats failed: {response.text}", response.status_code)
            
            # Test creating a listing with allow_cross_region=true
            listing_data = {
                "region": "Sapanca",
                "micro_location": "Göl kenarı",
                "concept": "Butik otel",
                "capacity_label": "4 kişi",
                "pax": 4,
                "date_start": "2025-03-01",
                "date_end": "2025-03-07", 
                "nights": 6,
                "price_min": 1400,
                "price_max": 1600,
                "availability_status": "available",
                "allow_cross_region": True,
                "room_type": "suite",
                "description": "Test listing for cross-region matching"
            }
            
            create_response = self.session.post(f"{BASE_URL}/listings", json=listing_data)
            
            if create_response.status_code == 200:
                new_listing = create_response.json()
                listing_id = new_listing.get("id") or new_listing.get("_id")
                self.log_test("/listings (with allow_cross_region=true)", "POST", True, f"Cross-region listing created: {listing_id}", 200)
                
                # Test filtering with include_cross_region=true
                filter_response = self.session.get(f"{BASE_URL}/listings", params={"include_cross_region": "true"})
                
                if filter_response.status_code == 200:
                    filtered_listings = filter_response.json()
                    cross_region_listings = [l for l in filtered_listings if l.get("allow_cross_region", False)]
                    self.log_test("/listings?include_cross_region=true", "GET", True, f"Cross-region filter returned {len(cross_region_listings)} cross-region listings", 200)
                else:
                    self.log_test("/listings?include_cross_region=true", "GET", False, f"Cross-region filtering failed: {filter_response.text}", filter_response.status_code)
                    
            else:
                self.log_test("/listings (with allow_cross_region=true)", "POST", False, f"Cross-region listing creation failed: {create_response.text}", create_response.status_code)
                
        except Exception as e:
            self.log_test("/cross-region functionality", "MIXED", False, f"Cross-region error: {str(e)}")
    
    def test_admin_endpoints(self):
        """Test admin-only endpoints (region management)"""
        try:
            # Test admin region pricing
            pricing_response = self.session.get(f"{BASE_URL}/admin/region-pricing")
            
            if pricing_response.status_code == 200:
                pricing_data = pricing_response.json()
                self.log_test("/admin/region-pricing", "GET", True, f"Retrieved pricing for {len(pricing_data)} regions", 200)
                
                # Test updating region pricing for Abant
                update_data = {"match_fee": 225}
                update_response = self.session.put(f"{BASE_URL}/admin/region-pricing/Abant", json=update_data)
                
                if update_response.status_code == 200:
                    self.log_test("/admin/region-pricing/Abant", "PUT", True, "Abant pricing updated to 225 TL", 200)
                else:
                    self.log_test("/admin/region-pricing/Abant", "PUT", False, f"Pricing update failed: {update_response.text}", update_response.status_code)
                    
                # Test admin revenue
                revenue_response = self.session.get(f"{BASE_URL}/admin/revenue")
                if revenue_response.status_code == 200:
                    revenue_data = revenue_response.json()
                    self.log_test("/admin/revenue", "GET", True, "Admin revenue data retrieved", 200)
                else:
                    self.log_test("/admin/revenue", "GET", False, f"Admin revenue failed: {revenue_response.text}", revenue_response.status_code)
                
                # Test admin region stats
                stats_response = self.session.get(f"{BASE_URL}/admin/region-stats")
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    self.log_test("/admin/region-stats", "GET", True, "Admin region stats retrieved", 200)
                else:
                    self.log_test("/admin/region-stats", "GET", False, f"Region stats failed: {stats_response.text}", stats_response.status_code)
            else:
                self.log_test("/admin/region-pricing", "GET", False, f"Admin access denied or failed: {pricing_response.text}", pricing_response.status_code)
                
        except Exception as e:
            self.log_test("/admin/*", "MIXED", False, f"Admin endpoints error: {str(e)}")
    
    def run_all_tests(self):
        """Run all API tests"""
        print("=" * 60)
        print("CapX Hotel Platform v4 Backend API Testing")
        print("=" * 60)
        
        # Authenticate first
        if not self.authenticate():
            print("❌ Authentication failed. Cannot proceed with tests.")
            return
        
        print("\n🧪 Running endpoint tests...\n")
        
        # Core v4 endpoints
        self.test_regions()
        self.test_general_stats()  # NEW: Test GET /api/stats for datetime errors
        self.test_enhanced_filters()
        self.test_payment_system()
        self.test_invoice_system()
        self.test_subscription_system()
        self.test_notification_system()
        self.test_revenue_reports()
        self.test_market_trends()
        self.test_performance_scores()
        self.test_request_statistics()
        self.test_cross_region_functionality()  # NEW: Test cross-region functionality
        self.test_kvkk_compliance()
        self.test_admin_endpoints()
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            print("-" * 40)
            for result in self.test_results:
                if not result["success"]:
                    print(f"• {result['method']} {result['endpoint']}")
                    print(f"  └── {result['details']}")
                    if result['status_code']:
                        print(f"  └── HTTP {result['status_code']}")
                    print()
        
        print("\n✅ PASSED TESTS:")
        print("-" * 40)
        for result in self.test_results:
            if result["success"]:
                print(f"• {result['method']} {result['endpoint']} - {result['details']}")

if __name__ == "__main__":
    tester = CapXAPITester()
    tester.run_all_tests()