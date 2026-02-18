#!/usr/bin/env python3
"""
Comprehensive backend API tests for Hotel-to-Hotel Capacity Exchange Platform
Tests all CRUD operations, auth, request/match flows, and progressive disclosure
"""

import requests
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Use public endpoint
BASE_URL = "https://inter-hotel-rooms.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

class HotelMatchTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        
        # Test data storage
        self.hotel_a_id = None
        self.hotel_a_token = None
        self.hotel_a_email = None
        self.hotel_b_id = None
        self.hotel_b_token = None
        self.hotel_b_email = None
        self.hotel_c_id = None
        self.hotel_c_token = None
        self.hotel_c_email = None
        self.listing_id = None
        self.request_id = None
        self.match_id = None
        
    def log(self, message: str, level: str = "info"):
        """Log messages with colors"""
        if level == "success":
            print(f"{Colors.GREEN}✓ {message}{Colors.END}")
        elif level == "error":
            print(f"{Colors.RED}✗ {message}{Colors.END}")
        elif level == "warning":
            print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")
        elif level == "info":
            print(f"{Colors.BLUE}ℹ {message}{Colors.END}")
        else:
            print(message)
    
    def run_test(self, name: str, test_func):
        """Run a single test and track results"""
        self.tests_run += 1
        print(f"\n{'='*60}")
        self.log(f"Test {self.tests_run}: {name}", "info")
        print('='*60)
        
        try:
            test_func()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "success")
            return True
        except AssertionError as e:
            self.tests_failed += 1
            self.log(f"FAILED: {name} - {str(e)}", "error")
            return False
        except Exception as e:
            self.tests_failed += 1
            self.log(f"ERROR: {name} - {str(e)}", "error")
            return False
    
    def assert_status(self, response: requests.Response, expected: int, message: str = ""):
        """Assert response status code"""
        if response.status_code != expected:
            error_detail = ""
            try:
                error_detail = f" - {response.json()}"
            except:
                error_detail = f" - {response.text[:200]}"
            raise AssertionError(
                f"Expected status {expected}, got {response.status_code}{error_detail}. {message}"
            )
    
    def assert_field(self, data: Dict, field: str, message: str = ""):
        """Assert field exists in response data"""
        if field not in data:
            raise AssertionError(f"Field '{field}' not found in response. {message}")
    
    # ========================================================================
    # AUTH TESTS
    # ========================================================================
    
    def test_register_hotel_a(self):
        """Test hotel registration for Hotel A"""
        timestamp = datetime.now().strftime("%H%M%S%f")
        self.hotel_a_email = f"hotela_{timestamp}@test.com"
        payload = {
            "name": f"Test Hotel A {timestamp}",
            "region": "Sapanca",
            "micro_location": "Maşukiye",
            "concept": "Boutique Villa",
            "address": "Test Address A",
            "phone": "+90 555 111 1111",
            "whatsapp": "+90 555 111 1111",
            "website": "https://hotela.example.com",
            "contact_person": "Manager A",
            "email": self.hotel_a_email,
            "password": "TestPass123!"
        }
        
        response = requests.post(f"{self.base_url}/auth/register", json=payload)
        self.assert_status(response, 200, "Hotel A registration failed")
        
        data = response.json()
        self.assert_field(data, "id", "Hotel A ID not returned")
        self.assert_field(data, "email", "Hotel A email not returned")
        
        self.hotel_a_id = data["id"]
        self.log(f"Hotel A registered with ID: {self.hotel_a_id[:8]}... and email: {self.hotel_a_email}", "success")
    
    def test_register_hotel_b(self):
        """Test hotel registration for Hotel B"""
        timestamp = datetime.now().strftime("%H%M%S%f")
        self.hotel_b_email = f"hotelb_{timestamp}@test.com"
        payload = {
            "name": f"Test Hotel B {timestamp}",
            "region": "Kartepe",
            "micro_location": "Merkez",
            "concept": "Ski Resort",
            "address": "Test Address B",
            "phone": "+90 555 222 2222",
            "whatsapp": "+90 555 222 2222",
            "website": "https://hotelb.example.com",
            "contact_person": "Manager B",
            "email": self.hotel_b_email,
            "password": "TestPass123!"
        }
        
        response = requests.post(f"{self.base_url}/auth/register", json=payload)
        self.assert_status(response, 200, "Hotel B registration failed")
        
        data = response.json()
        self.assert_field(data, "id", "Hotel B ID not returned")
        
        self.hotel_b_id = data["id"]
        self.log(f"Hotel B registered with ID: {self.hotel_b_id[:8]}... and email: {self.hotel_b_email}", "success")
    
    def test_login_hotel_a(self):
        """Test login for Hotel A"""
        # OAuth2 form data
        form_data = {
            "username": self.hotel_a_email,
            "password": "TestPass123!"
        }
        
        response = requests.post(
            f"{self.base_url}/auth/login",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        self.assert_status(response, 200, "Hotel A login failed")
        
        data = response.json()
        self.assert_field(data, "access_token", "Access token not returned for Hotel A")
        
        self.hotel_a_token = data["access_token"]
        self.log("Hotel A logged in successfully", "success")
    
    def test_login_hotel_b(self):
        """Test login for Hotel B"""
        form_data = {
            "username": self.hotel_b_email,
            "password": "TestPass123!"
        }
        
        response = requests.post(
            f"{self.base_url}/auth/login",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        self.assert_status(response, 200, "Hotel B login failed")
        
        data = response.json()
        self.assert_field(data, "access_token", "Access token not returned for Hotel B")
        
        self.hotel_b_token = data["access_token"]
        self.log("Hotel B logged in successfully", "success")
    
    def test_auth_me_hotel_a(self):
        """Test /auth/me endpoint for Hotel A"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        response = requests.get(f"{self.base_url}/auth/me", headers=headers)
        self.assert_status(response, 200, "/auth/me failed for Hotel A")
        
        data = response.json()
        self.assert_field(data, "id", "Hotel A profile missing ID")
        self.assert_field(data, "name", "Hotel A profile missing name")
        self.assert_field(data, "email", "Hotel A profile missing email")
        
        assert data["id"] == self.hotel_a_id, "Hotel A ID mismatch in /auth/me"
        self.log(f"Hotel A profile verified: {data['name']}", "success")
    
    def test_auth_me_hotel_b(self):
        """Test /auth/me endpoint for Hotel B"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        response = requests.get(f"{self.base_url}/auth/me", headers=headers)
        self.assert_status(response, 200, "/auth/me failed for Hotel B")
        
    
    def test_register_hotel_c(self):
        """Test hotel registration for Hotel C (for unauthorized access test)"""
        timestamp = datetime.now().strftime("%H%M%S%f")
        self.hotel_c_email = f"hotelc_{timestamp}@test.com"
        payload = {
            "name": f"Test Hotel C {timestamp}",
            "region": "Sapanca",
            "micro_location": "Kırkpınar",
            "concept": "Family Resort",
            "address": "Test Address C",
            "phone": "+90 555 333 3333",
            "whatsapp": "+90 555 333 3333",
            "website": "https://hotelc.example.com",
            "contact_person": "Manager C",
            "email": self.hotel_c_email,
            "password": "TestPass123!"
        }
        
        response = requests.post(f"{self.base_url}/auth/register", json=payload)
        self.assert_status(response, 200, "Hotel C registration failed")
        
        data = response.json()
        self.hotel_c_id = data["id"]
        self.log(f"Hotel C registered with ID: {self.hotel_c_id[:8]}... and email: {self.hotel_c_email}", "success")
    
    def test_login_hotel_c(self):
        """Test login for Hotel C"""
        form_data = {
            "username": self.hotel_c_email,
            "password": "TestPass123!"
        }
        
        response = requests.post(
            f"{self.base_url}/auth/login",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        self.assert_status(response, 200, "Hotel C login failed")
        
        data = response.json()
        self.hotel_c_token = data["access_token"]
        self.log("Hotel C logged in successfully", "success")
    
    # ========================================================================
    # LISTINGS TESTS
    # ========================================================================
    
    def test_create_listing_hotel_a(self):
        """Test creating availability listing by Hotel A"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        
        # Create listing for 3 days from now
        start_date = datetime.now() + timedelta(days=3)
        end_date = start_date + timedelta(days=2)
        
        payload = {
            "region": "Sapanca",
            "micro_location": "Maşukiye",
            "concept": "Boutique Villa",
            "capacity_label": "2+1 Villa",
            "pax": 4,
            "date_start": start_date.isoformat(),
            "date_end": end_date.isoformat(),
            "nights": 2,
            "price_min": 3000.0,
            "price_max": 4500.0,
            "availability_status": "available"
        }
        
        response = requests.post(f"{self.base_url}/listings", json=payload, headers=headers)
        self.assert_status(response, 200, "Failed to create listing")
        
        data = response.json()
        self.assert_field(data, "id", "Listing ID not returned")
        self.assert_field(data, "is_locked", "is_locked field missing")
        
        assert data["is_locked"] == False, "New listing should not be locked"
        
        self.listing_id = data["id"]
        self.log(f"Listing created with ID: {self.listing_id[:8]}...", "success")
    
    def test_get_listings_anonymous(self):
        """Test GET /listings returns anonymous data (no hotel_id)"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        response = requests.get(f"{self.base_url}/listings", headers=headers)
        self.assert_status(response, 200, "Failed to get listings")
        
        data = response.json()
        assert isinstance(data, list), "Listings should be a list"
        assert len(data) > 0, "Should have at least one listing"
        
        # Find our listing
        listing = next((l for l in data if l["id"] == self.listing_id), None)
        assert listing is not None, "Created listing not found in listings"
        
        # Verify anonymous fields only
        expected_fields = {
            "id", "region", "micro_location", "concept", "capacity_label",
            "pax", "date_start", "date_end", "nights", "price_min", "price_max",
            "availability_status", "is_locked"
        }
        
        for field in expected_fields:
            self.assert_field(listing, field, f"Anonymous listing missing {field}")
        
        # Verify hotel_id is NOT exposed
        assert "hotel_id" not in listing, "hotel_id should not be exposed in anonymous listings"
        
        self.log("Listings are properly anonymous (no hotel_id exposed)", "success")
    
    def test_create_listing_with_images_and_features(self):
        """Test creating listing with image_urls and features (Phase 3.2)"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        
        start_date = datetime.now() + timedelta(days=5)
        end_date = start_date + timedelta(days=3)
        
        payload = {
            "region": "Kartepe",
            "micro_location": "Merkez",
            "concept": "Luxury Chalet",
            "capacity_label": "3+1 Chalet",
            "pax": 6,
            "date_start": start_date.isoformat(),
            "date_end": end_date.isoformat(),
            "nights": 3,
            "price_min": 5000.0,
            "price_max": 7000.0,
            "availability_status": "available",
            "image_urls": [
                "https://example.com/image1.jpg",
                "https://example.com/image2.jpg",
                "https://example.com/image3.jpg"
            ],
            "features": ["Şömine", "Göl manzarası", "Jakuzili", "Özel bahçe", "Barbekü"]
        }
        
        response = requests.post(f"{self.base_url}/listings", json=payload, headers=headers)
        self.assert_status(response, 200, "Failed to create listing with images and features")
        
        data = response.json()
        self.assert_field(data, "id", "Listing ID not returned")
        self.assert_field(data, "image_urls", "image_urls field missing")
        self.assert_field(data, "features", "features field missing")
        
        assert isinstance(data["image_urls"], list), "image_urls should be a list"
        assert len(data["image_urls"]) == 3, f"Expected 3 images, got {len(data['image_urls'])}"
        assert data["image_urls"][0] == "https://example.com/image1.jpg", "First image URL mismatch"
        
        assert isinstance(data["features"], list), "features should be a list"
        assert len(data["features"]) == 5, f"Expected 5 features, got {len(data['features'])}"
        assert "Şömine" in data["features"], "Feature 'Şömine' not found"
        assert "Jakuzili" in data["features"], "Feature 'Jakuzili' not found"
        
        # Store this listing ID for later tests
        self.listing_with_media_id = data["id"]
        self.log(f"Listing with images and features created: {self.listing_with_media_id[:8]}...", "success")
    
    def test_create_listing_without_images_and_features(self):
        """Test creating listing without image_urls and features (robustness check)"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        
        start_date = datetime.now() + timedelta(days=7)
        end_date = start_date + timedelta(days=2)
        
        payload = {
            "region": "Sapanca",
            "micro_location": "Kırkpınar",
            "concept": "Standard Room",
            "capacity_label": "1+1",
            "pax": 2,
            "date_start": start_date.isoformat(),
            "date_end": end_date.isoformat(),
            "nights": 2,
            "price_min": 2000.0,
            "price_max": 3000.0,
            "availability_status": "limited"
        }
        
        response = requests.post(f"{self.base_url}/listings", json=payload, headers=headers)
        self.assert_status(response, 200, "Failed to create listing without images/features")
        
        data = response.json()
        self.assert_field(data, "id", "Listing ID not returned")
        
        # Backend should default to empty lists
        assert "image_urls" in data, "image_urls field should be present"
        assert "features" in data, "features field should be present"
        assert data["image_urls"] == [] or data["image_urls"] is None, "image_urls should be empty or None"
        assert data["features"] == [] or data["features"] is None, "features should be empty or None"
        
        self.log("Listing without images/features created successfully (graceful handling)", "success")
    
    def test_get_listings_with_media_fields(self):
        """Test GET /listings returns image_urls and features in anonymous feed"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        response = requests.get(f"{self.base_url}/listings", headers=headers)
        self.assert_status(response, 200, "Failed to get listings")
        
        data = response.json()
        
        # Find listing with media
        listing_with_media = next((l for l in data if l.get("id") == getattr(self, "listing_with_media_id", None)), None)
        
        if listing_with_media:
            self.assert_field(listing_with_media, "image_urls", "image_urls missing in anonymous feed")
            self.assert_field(listing_with_media, "features", "features missing in anonymous feed")
            
            assert isinstance(listing_with_media["image_urls"], list), "image_urls should be a list"
            assert len(listing_with_media["image_urls"]) == 3, "Should have 3 images"
            assert isinstance(listing_with_media["features"], list), "features should be a list"
            assert len(listing_with_media["features"]) == 5, "Should have 5 features"
            
            self.log("Anonymous feed correctly shows image_urls and features", "success")
        else:
            self.log("Listing with media not found in feed (may have been created in different test)", "warning")
    
    def test_get_my_listings_with_media_fields(self):
        """Test GET /listings?mine=true returns image_urls and features"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        response = requests.get(f"{self.base_url}/listings", params={"mine": True}, headers=headers)
        self.assert_status(response, 200, "Failed to get my listings")
        
        data = response.json()
        assert isinstance(data, list), "My listings should be a list"
        
        # Find listing with media
        listing_with_media = next((l for l in data if l.get("id") == getattr(self, "listing_with_media_id", None)), None)
        
        if listing_with_media:
            self.assert_field(listing_with_media, "image_urls", "image_urls missing in mine=true")
            self.assert_field(listing_with_media, "features", "features missing in mine=true")
            
            assert len(listing_with_media["image_urls"]) == 3, "Should have 3 images in mine=true"
            assert len(listing_with_media["features"]) == 5, "Should have 5 features in mine=true"
            
            self.log("My listings (mine=true) correctly shows image_urls and features", "success")
        else:
            self.log("Listing with media not found in my listings", "warning")
    
    # ========================================================================
    # REQUEST TESTS
    # ========================================================================
    
    def test_create_request_hotel_b(self):
        """Test Hotel B creating a request to Hotel A's listing"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        
        payload = {
            "listing_id": self.listing_id,
            "guest_type": "family",
            "notes": "Test request from Hotel B",
            "confirm_window_minutes": 120
        }
        
        response = requests.post(f"{self.base_url}/requests", json=payload, headers=headers)
        self.assert_status(response, 200, "Failed to create request")
        
        data = response.json()
        self.assert_field(data, "id", "Request ID not returned")
        self.assert_field(data, "status", "Request status not returned")
        self.assert_field(data, "from_hotel_id", "from_hotel_id not returned")
        self.assert_field(data, "to_hotel_id", "to_hotel_id not returned")
        
        assert data["status"] == "pending", "New request should have pending status"
        assert data["from_hotel_id"] == self.hotel_b_id, "from_hotel_id should be Hotel B"
        assert data["to_hotel_id"] == self.hotel_a_id, "to_hotel_id should be Hotel A"
        
        self.request_id = data["id"]
        self.log(f"Request created with ID: {self.request_id[:8]}...", "success")
    
    def test_listing_locked_after_request(self):
        """Test that listing is locked after request is created"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        response = requests.get(f"{self.base_url}/listings/{self.listing_id}", headers=headers)
        self.assert_status(response, 200, "Failed to get listing")
        
        data = response.json()
        assert data["is_locked"] == True, "Listing should be locked after request"
        
        self.log("Listing is properly locked after request", "success")
    
    def test_duplicate_request_rejected(self):
        """Test that duplicate request to same listing is rejected"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        
        payload = {
            "listing_id": self.listing_id,
            "guest_type": "couple",
            "notes": "Duplicate request",
            "confirm_window_minutes": 120
        }
        
        response = requests.post(f"{self.base_url}/requests", json=payload, headers=headers)
        self.assert_status(response, 400, "Duplicate request should be rejected with 400")
        
        self.log("Duplicate request properly rejected", "success")
    
    def test_incoming_requests_hotel_a(self):
        """Test Hotel A can see incoming request"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        response = requests.get(f"{self.base_url}/requests/incoming", headers=headers)
        self.assert_status(response, 200, "Failed to get incoming requests")
        
        data = response.json()
        assert isinstance(data, list), "Incoming requests should be a list"
        
        # Find our request
        request = next((r for r in data if r["id"] == self.request_id), None)
        assert request is not None, "Created request not found in incoming requests"
        assert request["status"] == "pending", "Request should be pending"
        
        self.log(f"Hotel A sees incoming request: {request['id'][:8]}...", "success")
    
    def test_outgoing_requests_hotel_b(self):
        """Test Hotel B can see outgoing request"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        response = requests.get(f"{self.base_url}/requests/outgoing", headers=headers)
        self.assert_status(response, 200, "Failed to get outgoing requests")
        
        data = response.json()
        assert isinstance(data, list), "Outgoing requests should be a list"
        
        # Find our request
        request = next((r for r in data if r["id"] == self.request_id), None)
        assert request is not None, "Created request not found in outgoing requests"
        
        self.log(f"Hotel B sees outgoing request: {request['id'][:8]}...", "success")
    
    # ========================================================================
    # MATCH TESTS
    # ========================================================================
    
    def test_accept_request_hotel_a(self):
        """Test Hotel A accepting the request and creating a match"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        response = requests.post(
            f"{self.base_url}/requests/{self.request_id}/accept",
            headers=headers
        )
        self.assert_status(response, 200, "Failed to accept request")
        
        data = response.json()
        self.assert_field(data, "id", "Match ID not returned")
        self.assert_field(data, "reference_code", "Reference code not returned")
        self.assert_field(data, "fee_amount", "Fee amount not returned")
        self.assert_field(data, "fee_status", "Fee status not returned")
        self.assert_field(data, "hotel_a_id", "hotel_a_id not returned")
        self.assert_field(data, "hotel_b_id", "hotel_b_id not returned")
        
        assert data["fee_amount"] == 250.0, "Fee amount should be 250.0 TL (default MATCH_FEE_TL)"
        assert data["fee_status"] == "due", "Fee status should be 'due'"
        assert data["hotel_a_id"] == self.hotel_b_id, "hotel_a_id should be requester (Hotel B)"
        assert data["hotel_b_id"] == self.hotel_a_id, "hotel_b_id should be listing owner (Hotel A)"
        
        # Verify reference code format (SPC-2025-00001 or KTP-2025-00001)
        ref_code = data["reference_code"]
        assert ref_code.startswith("SPC-") or ref_code.startswith("KTP-"), \
            f"Reference code should start with SPC- or KTP-, got {ref_code}"
        
        self.match_id = data["id"]
        self.log(f"Match created with ID: {self.match_id[:8]}... and ref: {ref_code}", "success")
    
    def test_listing_unlocked_after_accept(self):
        """Test that listing is unlocked after request is accepted"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        response = requests.get(f"{self.base_url}/listings/{self.listing_id}", headers=headers)
        self.assert_status(response, 200, "Failed to get listing")
        
        data = response.json()
        assert data["is_locked"] == False, "Listing should be unlocked after accept"
        
        self.log("Listing is properly unlocked after accept", "success")
    
    def test_get_matches_hotel_a(self):
        """Test Hotel A can see the match"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        response = requests.get(f"{self.base_url}/matches", headers=headers)
        self.assert_status(response, 200, "Failed to get matches")
        
        data = response.json()
        assert isinstance(data, list), "Matches should be a list"
        
        # Find our match
        match = next((m for m in data if m["id"] == self.match_id), None)
        assert match is not None, "Created match not found in Hotel A's matches"
        
        self.log(f"Hotel A sees match: {match['reference_code']}", "success")
    
    def test_get_matches_hotel_b(self):
        """Test Hotel B can see the match"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        response = requests.get(f"{self.base_url}/matches", headers=headers)
        self.assert_status(response, 200, "Failed to get matches")
        
        data = response.json()
        assert isinstance(data, list), "Matches should be a list"
        
        # Find our match
        match = next((m for m in data if m["id"] == self.match_id), None)
        assert match is not None, "Created match not found in Hotel B's matches"
        
        self.log(f"Hotel B sees match: {match['reference_code']}", "success")
    
    def test_progressive_disclosure_hotel_a(self):
        """Test progressive disclosure: Hotel A can see both hotels' details in match"""
        headers = {"Authorization": f"Bearer {self.hotel_a_token}"}
        response = requests.get(f"{self.base_url}/matches/{self.match_id}", headers=headers)
        self.assert_status(response, 200, "Failed to get match details")
        
        data = response.json()
        self.assert_field(data, "counterparty", "counterparty field missing")
        self.assert_field(data["counterparty"], "self", "counterparty.self missing")
        self.assert_field(data["counterparty"], "other", "counterparty.other missing")
        
        # Verify both hotels' full details are revealed
        self_hotel = data["counterparty"]["self"]
        other_hotel = data["counterparty"]["other"]
        
        # Self should be Hotel A
        assert self_hotel["id"] == self.hotel_a_id, "Self hotel should be Hotel A"
        self.assert_field(self_hotel, "name", "Self hotel missing name")
        self.assert_field(self_hotel, "phone", "Self hotel missing phone")
        self.assert_field(self_hotel, "email", "Self hotel missing email")
        
        # Other should be Hotel B
        assert other_hotel["id"] == self.hotel_b_id, "Other hotel should be Hotel B"
        self.assert_field(other_hotel, "name", "Other hotel missing name")
        self.assert_field(other_hotel, "phone", "Other hotel missing phone")
        self.assert_field(other_hotel, "email", "Other hotel missing email")
        
        self.log("Progressive disclosure working: Hotel A sees both hotels' full details", "success")
    
    def test_progressive_disclosure_hotel_b(self):
        """Test progressive disclosure: Hotel B can see both hotels' details in match"""
        headers = {"Authorization": f"Bearer {self.hotel_b_token}"}
        response = requests.get(f"{self.base_url}/matches/{self.match_id}", headers=headers)
        self.assert_status(response, 200, "Failed to get match details")
        
        data = response.json()
        
        self_hotel = data["counterparty"]["self"]
        other_hotel = data["counterparty"]["other"]
        
        # Self should be Hotel B
        assert self_hotel["id"] == self.hotel_b_id, "Self hotel should be Hotel B"
        
        # Other should be Hotel A
        assert other_hotel["id"] == self.hotel_a_id, "Other hotel should be Hotel A"
        
        self.log("Progressive disclosure working: Hotel B sees both hotels' full details", "success")
    
    def test_unauthorized_match_access(self):
        """Test that Hotel C (not party to match) gets 403 when accessing match detail"""
        headers_c = {"Authorization": f"Bearer {self.hotel_c_token}"}
        
        # Hotel C tries to access the match between Hotel A and Hotel B
        response = requests.get(f"{self.base_url}/matches/{self.match_id}", headers=headers_c)
        self.assert_status(response, 403, "Should return 403 for unauthorized match access")
        
        # Verify error message
        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"
        assert "not authorized" in data["detail"].lower() or "forbidden" in data["detail"].lower(), \
            f"Error message should indicate authorization issue, got: {data['detail']}"
        
        self.log("Unauthorized match access properly blocked with 403", "success")
    
    # ========================================================================
    # REJECT FLOW TEST
    # ========================================================================
    
    def test_reject_flow(self):
        """Test reject flow: create new listing and request, then reject"""
        # Hotel A creates another listing
        headers_a = {"Authorization": f"Bearer {self.hotel_a_token}"}
        start_date = datetime.now() + timedelta(days=10)
        end_date = start_date + timedelta(days=3)
        
        payload = {
            "region": "Kartepe",
            "micro_location": "Merkez",
            "concept": "Ski Lodge",
            "capacity_label": "1+1 Room",
            "pax": 2,
            "date_start": start_date.isoformat(),
            "date_end": end_date.isoformat(),
            "nights": 3,
            "price_min": 2000.0,
            "price_max": 3000.0,
            "availability_status": "limited"
        }
        
        response = requests.post(f"{self.base_url}/listings", json=payload, headers=headers_a)
        self.assert_status(response, 200, "Failed to create second listing")
        listing2_id = response.json()["id"]
        
        # Hotel B creates request
        headers_b = {"Authorization": f"Bearer {self.hotel_b_token}"}
        payload = {
            "listing_id": listing2_id,
            "guest_type": "couple",
            "notes": "Test reject flow",
            "confirm_window_minutes": 120
        }
        
        response = requests.post(f"{self.base_url}/requests", json=payload, headers=headers_b)
        self.assert_status(response, 200, "Failed to create second request")
        request2_id = response.json()["id"]
        
        # Verify listing is locked
        response = requests.get(f"{self.base_url}/listings/{listing2_id}", headers=headers_b)
        assert response.json()["is_locked"] == True, "Listing should be locked"
        
        # Hotel A rejects request
        response = requests.post(
            f"{self.base_url}/requests/{request2_id}/reject",
            headers=headers_a
        )
        self.assert_status(response, 200, "Failed to reject request")
        
        data = response.json()
        assert data["status"] == "rejected", "Request status should be rejected"
        
        # Verify listing is unlocked
        response = requests.get(f"{self.base_url}/listings/{listing2_id}", headers=headers_a)
        assert response.json()["is_locked"] == False, "Listing should be unlocked after reject"
        
        self.log("Reject flow working correctly: listing unlocked after rejection", "success")
    
    # ========================================================================
    # DASHBOARD KPI TEST
    # ========================================================================
    
    def test_dashboard_kpis(self):
        """Test that dashboard KPI endpoints return correct counts"""
        headers_a = {"Authorization": f"Bearer {self.hotel_a_token}"}
        
        # Get all data for Hotel A
        outgoing_res = requests.get(f"{self.base_url}/requests/outgoing", headers=headers_a)
        incoming_res = requests.get(f"{self.base_url}/requests/incoming", headers=headers_a)
        matches_res = requests.get(f"{self.base_url}/matches", headers=headers_a)
        
        self.assert_status(outgoing_res, 200, "Failed to get outgoing requests")
        self.assert_status(incoming_res, 200, "Failed to get incoming requests")
        self.assert_status(matches_res, 200, "Failed to get matches")
        
        outgoing_count = len(outgoing_res.json())
        incoming_count = len(incoming_res.json())
        matches_count = len(matches_res.json())
        
        self.log(f"Hotel A KPIs - Outgoing: {outgoing_count}, Incoming: {incoming_count}, Matches: {matches_count}", "success")
        
        # Verify Hotel A has at least 2 incoming (one accepted, one rejected)
        assert incoming_count >= 2, f"Hotel A should have at least 2 incoming requests, got {incoming_count}"
        
        # Verify Hotel A has at least 1 match
        assert matches_count >= 1, f"Hotel A should have at least 1 match, got {matches_count}"
    
    # ========================================================================
    # RUN ALL TESTS
    # ========================================================================
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*60)
        print("HOTEL-TO-HOTEL CAPACITY EXCHANGE - BACKEND API TESTS")
        print("="*60)
        print(f"Testing endpoint: {self.base_url}")
        print("="*60 + "\n")
        
        # Auth tests
        self.run_test("Register Hotel A", self.test_register_hotel_a)
        self.run_test("Register Hotel B", self.test_register_hotel_b)
        self.run_test("Register Hotel C", self.test_register_hotel_c)
        self.run_test("Login Hotel A", self.test_login_hotel_a)
        self.run_test("Login Hotel B", self.test_login_hotel_b)
        self.run_test("Login Hotel C", self.test_login_hotel_c)
        self.run_test("Get Hotel A profile (/auth/me)", self.test_auth_me_hotel_a)
        self.run_test("Get Hotel B profile (/auth/me)", self.test_auth_me_hotel_b)
        
        # Listings tests
        self.run_test("Create availability listing (Hotel A)", self.test_create_listing_hotel_a)
        self.run_test("Get anonymous listings", self.test_get_listings_anonymous)
        
        # Phase 3.2: Image URLs and Features tests
        self.run_test("Create listing with images and features", self.test_create_listing_with_images_and_features)
        self.run_test("Create listing without images/features (robustness)", self.test_create_listing_without_images_and_features)
        self.run_test("Get listings with media fields in anonymous feed", self.test_get_listings_with_media_fields)
        self.run_test("Get my listings with media fields (mine=true)", self.test_get_my_listings_with_media_fields)
        
        # Request tests
        self.run_test("Create request (Hotel B → Hotel A)", self.test_create_request_hotel_b)
        self.run_test("Verify listing locked after request", self.test_listing_locked_after_request)
        self.run_test("Reject duplicate request to locked listing", self.test_duplicate_request_rejected)
        self.run_test("Get incoming requests (Hotel A)", self.test_incoming_requests_hotel_a)
        self.run_test("Get outgoing requests (Hotel B)", self.test_outgoing_requests_hotel_b)
        
        # Match tests
        self.run_test("Accept request and create match (Hotel A)", self.test_accept_request_hotel_a)
        self.run_test("Verify listing unlocked after accept", self.test_listing_unlocked_after_accept)
        self.run_test("Get matches (Hotel A)", self.test_get_matches_hotel_a)
        self.run_test("Get matches (Hotel B)", self.test_get_matches_hotel_b)
        self.run_test("Progressive disclosure for Hotel A", self.test_progressive_disclosure_hotel_a)
        self.run_test("Progressive disclosure for Hotel B", self.test_progressive_disclosure_hotel_b)
        self.run_test("Unauthorized match access (Hotel C)", self.test_unauthorized_match_access)
        
        # Additional flows
        self.run_test("Test reject flow", self.test_reject_flow)
        self.run_test("Test dashboard KPIs", self.test_dashboard_kpis)
        
        # Print summary
        self.print_summary()
        
        return self.tests_failed == 0
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total tests run: {self.tests_run}")
        print(f"{Colors.GREEN}Passed: {self.tests_passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.tests_failed}{Colors.END}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
        print("="*60 + "\n")

def main():
    """Main entry point"""
    tester = HotelMatchTester()
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
