#!/usr/bin/env python3
"""
CapX Platform V6 Backend Test Suite
Testing V6 improvements: Security, Pagination, Search, PDF Export, Activity Logs
"""
import asyncio
import os
import sys
import json
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Environment URLs
BACKEND_URL = "https://improvement-guide-2.preview.emergentagent.com/api"
TEST_CREDENTIALS = {"username": "admin@test.com", "password": "Admin123"}

class CapXV6Tester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.token = None
        self.test_results = []
        self.session = requests.Session()
        
    def log_test(self, test_name: str, success: bool, details: str = "", data: Any = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {test_name}: {details}")
        
    def authenticate(self) -> bool:
        """Authenticate and get bearer token"""
        try:
            # Use form data as specified in the review request
            response = self.session.post(
                f"{self.backend_url}/auth/login",
                data=TEST_CREDENTIALS,  # Form data, not JSON
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                self.log_test("Authentication", True, f"Successfully authenticated as {TEST_CREDENTIALS['username']}")
                return True
            else:
                self.log_test("Authentication", False, f"Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.log_test("Authentication", False, f"Login error: {str(e)}")
            return False

    def test_password_validation(self):
        """Test V6 Feature 1: Password validation with weak passwords"""
        print("\n=== Testing V6 Feature 1: Password Validation ===")
        
        weak_passwords = [
            ("123", "Too short and no uppercase/lowercase"),
            ("abc", "Too short and no digits/uppercase"),
            ("password", "No digits/uppercase"), 
            ("PASSWORD", "No digits/lowercase"),
            ("12345678", "No letters"),
            ("Passw", "Too short")
        ]
        
        test_hotel = {
            "name": "Test Hotel Password",
            "region": "Sapanca", 
            "micro_location": "Test Location",
            "concept": "Test Concept",
            "address": "Test Address",
            "phone": "+905551234567",
            "email": f"test_pass_{datetime.now().timestamp()}@example.com"
        }
        
        for weak_pass, description in weak_passwords:
            try:
                payload = {**test_hotel, "password": weak_pass}
                response = self.session.post(f"{self.backend_url}/auth/register", json=payload)
                
                if response.status_code == 400:
                    error_detail = response.json().get("detail", "")
                    if any(keyword in error_detail.lower() for keyword in ["şifre", "password", "karakter", "büyük", "rakam"]):
                        self.log_test(f"Password Validation - {weak_pass}", True, 
                                    f"Correctly rejected weak password: {error_detail}")
                    else:
                        self.log_test(f"Password Validation - {weak_pass}", False, 
                                    f"Rejected but wrong error message: {error_detail}")
                else:
                    self.log_test(f"Password Validation - {weak_pass}", False, 
                                f"Should have rejected weak password but got: {response.status_code}")
                    
            except Exception as e:
                self.log_test(f"Password Validation - {weak_pass}", False, f"Test error: {str(e)}")

    def test_pagination_headers(self):
        """Test V6 Feature 2: Pagination with X-Total-Count headers"""
        print("\n=== Testing V6 Feature 2: Pagination Headers ===")
        
        endpoints = [
            ("/listings", "skip=0&limit=5"),
            ("/requests/outgoing", "skip=0&limit=10"),
            ("/matches", "skip=0&limit=10"),
            ("/payments", "skip=0&limit=10"),
            ("/invoices", "skip=0&limit=10")
        ]
        
        for endpoint, params in endpoints:
            try:
                response = self.session.get(f"{self.backend_url}{endpoint}?{params}")
                
                if response.status_code == 200:
                    total_count_header = response.headers.get("X-Total-Count")
                    if total_count_header is not None:
                        self.log_test(f"Pagination - {endpoint}", True, 
                                    f"X-Total-Count header found: {total_count_header}")
                    else:
                        self.log_test(f"Pagination - {endpoint}", False, 
                                    f"Missing X-Total-Count header in response")
                else:
                    self.log_test(f"Pagination - {endpoint}", False, 
                                f"Request failed: {response.status_code}")
                    
            except Exception as e:
                self.log_test(f"Pagination - {endpoint}", False, f"Test error: {str(e)}")

    def test_fulltext_search(self):
        """Test V6 Feature 3: Full-text search functionality"""
        print("\n=== Testing V6 Feature 3: Full-text Search ===")
        
        search_terms = ["bungalov", "göl", "test", "sapanca"]
        
        for term in search_terms:
            try:
                response = self.session.get(f"{self.backend_url}/listings?search={term}")
                
                if response.status_code == 200:
                    results = response.json()
                    self.log_test(f"Full-text Search - {term}", True, 
                                f"Search completed, found {len(results)} results")
                else:
                    self.log_test(f"Full-text Search - {term}", False, 
                                f"Search failed: {response.status_code}")
                    
            except Exception as e:
                self.log_test(f"Full-text Search - {term}", False, f"Test error: {str(e)}")

    def test_pdf_invoice_export(self):
        """Test V6 Feature 4: PDF Invoice Export"""
        print("\n=== Testing V6 Feature 4: PDF Invoice Export ===")
        
        try:
            # First get list of invoices
            response = self.session.get(f"{self.backend_url}/invoices")
            
            if response.status_code == 200:
                invoices = response.json()
                if invoices:
                    # Test PDF export for first invoice
                    invoice_id = invoices[0]["id"]
                    pdf_response = self.session.get(f"{self.backend_url}/invoices/{invoice_id}/pdf")
                    
                    if pdf_response.status_code == 200:
                        content_type = pdf_response.headers.get("Content-Type", "")
                        if "application/pdf" in content_type:
                            pdf_size = len(pdf_response.content)
                            self.log_test("PDF Invoice Export", True, 
                                        f"PDF generated successfully, size: {pdf_size} bytes, Content-Type: {content_type}")
                        else:
                            self.log_test("PDF Invoice Export", False, 
                                        f"Wrong content type: {content_type}")
                    else:
                        self.log_test("PDF Invoice Export", False, 
                                    f"PDF generation failed: {pdf_response.status_code}")
                else:
                    self.log_test("PDF Invoice Export", False, "No invoices found to test PDF export")
            else:
                self.log_test("PDF Invoice Export", False, 
                            f"Could not retrieve invoices: {response.status_code}")
                
        except Exception as e:
            self.log_test("PDF Invoice Export", False, f"Test error: {str(e)}")

    def test_admin_activity_logs(self):
        """Test V6 Feature 5: Admin Activity Logs"""
        print("\n=== Testing V6 Feature 5: Admin Activity Logs ===")
        
        try:
            response = self.session.get(f"{self.backend_url}/admin/activity-logs?limit=10")
            
            if response.status_code == 200:
                logs = response.json()
                if logs:
                    # Check if logs have required actor_name field
                    first_log = logs[0]
                    if "actor_name" in first_log:
                        self.log_test("Admin Activity Logs", True, 
                                    f"Retrieved {len(logs)} activity logs with actor_name field")
                    else:
                        # Check available fields
                        available_fields = list(first_log.keys())
                        self.log_test("Admin Activity Logs", False, 
                                    f"Missing actor_name field. Available fields: {available_fields}")
                else:
                    self.log_test("Admin Activity Logs", True, 
                                "Activity logs endpoint working (no logs available)")
            elif response.status_code == 403:
                self.log_test("Admin Activity Logs", False, 
                            "Admin access denied - user may not have admin privileges")
            else:
                self.log_test("Admin Activity Logs", False, 
                            f"Request failed: {response.status_code}")
                
        except Exception as e:
            self.log_test("Admin Activity Logs", False, f"Test error: {str(e)}")

    def test_existing_endpoints(self):
        """Test V6 Feature 6: Verify existing endpoints still work"""
        print("\n=== Testing V6 Feature 6: Existing Endpoints ===")
        
        endpoints = [
            ("/stats", True),  # Requires auth
            ("/regions", True),  # Requires auth  
            ("/performance/health", False)  # No auth needed
        ]
        
        for endpoint, needs_auth in endpoints:
            try:
                if needs_auth:
                    response = self.session.get(f"{self.backend_url}{endpoint}")
                else:
                    # Remove auth header temporarily
                    headers = dict(self.session.headers)
                    if "Authorization" in headers:
                        del headers["Authorization"]
                    response = requests.get(f"{self.backend_url}{endpoint}", headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_test(f"Existing Endpoint - {endpoint}", True, 
                                f"Endpoint working correctly, returned {len(str(data))} chars")
                else:
                    self.log_test(f"Existing Endpoint - {endpoint}", False, 
                                f"Request failed: {response.status_code}")
                    
            except Exception as e:
                self.log_test(f"Existing Endpoint - {endpoint}", False, f"Test error: {str(e)}")

    def create_test_data_for_pdf(self):
        """Create test data flow for PDF testing if needed"""
        print("\n=== Setting up test data for PDF export ===")
        
        try:
            # Check if we have existing data
            invoices_response = self.session.get(f"{self.backend_url}/invoices")
            if invoices_response.status_code == 200:
                invoices = invoices_response.json()
                if invoices:
                    self.log_test("Test Data Setup", True, f"Found {len(invoices)} existing invoices")
                    return
            
            # If no invoices, check for matches to create a payment
            matches_response = self.session.get(f"{self.backend_url}/matches")
            if matches_response.status_code == 200:
                matches = matches_response.json()
                if matches:
                    # Try to create a payment for the first match
                    match_id = matches[0]["id"]
                    payment_data = {"match_id": match_id, "method": "mock"}
                    
                    payment_response = self.session.post(f"{self.backend_url}/payments/initiate", json=payment_data)
                    if payment_response.status_code == 200:
                        payment = payment_response.json()
                        payment_id = payment["id"]
                        
                        # Complete the payment to generate invoice
                        complete_response = self.session.post(f"{self.backend_url}/payments/{payment_id}/complete")
                        if complete_response.status_code == 200:
                            self.log_test("Test Data Setup", True, "Created test payment and invoice for PDF testing")
                        else:
                            self.log_test("Test Data Setup", False, f"Could not complete payment: {complete_response.status_code}")
                    else:
                        self.log_test("Test Data Setup", False, f"Could not create payment: {payment_response.status_code}")
                else:
                    self.log_test("Test Data Setup", False, "No matches available for creating test payment")
            else:
                self.log_test("Test Data Setup", False, f"Could not retrieve matches: {matches_response.status_code}")
                
        except Exception as e:
            self.log_test("Test Data Setup", False, f"Setup error: {str(e)}")

    def run_all_tests(self):
        """Run all V6 feature tests"""
        print("🚀 Starting CapX Platform V6 Backend Testing")
        print("=" * 60)
        
        # Authenticate first
        if not self.authenticate():
            print("❌ Authentication failed, cannot proceed with tests")
            return
        
        # Test V6 Features
        self.test_password_validation()
        self.test_pagination_headers()
        self.test_fulltext_search()
        
        # Setup test data if needed for PDF testing
        self.create_test_data_for_pdf()
        self.test_pdf_invoice_export()
        
        self.test_admin_activity_logs()
        self.test_existing_endpoints()
        
        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("🏁 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  • {result['test']}: {result['details']}")
        
        print(f"\n🎯 V6 FEATURES TESTED:")
        print(f"  1. ✅ Security - Password Validation")
        print(f"  2. ✅ Pagination with X-Total-Count Headers")
        print(f"  3. ✅ Full-text Search on Listings")
        print(f"  4. ✅ PDF Invoice Export")
        print(f"  5. ✅ Admin Activity Logs")
        print(f"  6. ✅ Existing Endpoints Compatibility")


if __name__ == "__main__":
    tester = CapXV6Tester()
    tester.run_all_tests()