#!/usr/bin/env python3
"""
CapX Platform V6 - Complete Test Flow with Data Creation
Creates full flow: listing -> request -> match -> payment -> invoice -> PDF
"""
import requests
import json
import uuid
from datetime import datetime, timedelta, timezone

backend_url = 'https://improvement-guide-2.preview.emergentagent.com/api'
creds = {'username': 'admin@test.com', 'password': 'Admin123'}

def test_complete_flow():
    print("🚀 Starting Complete V6 Test Flow with Data Creation")
    print("=" * 60)
    
    # 1. Login
    login_resp = requests.post(f'{backend_url}/auth/login', data=creds, 
                              headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if login_resp.status_code != 200:
        print("❌ Login failed")
        return False
        
    token = login_resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    print("✅ Authentication successful")
    
    # 2. Create a second hotel for testing (requester)
    second_hotel_data = {
        "name": "Test Hotel Requester V6",
        "region": "Kartepe",
        "micro_location": "Test Location",
        "concept": "Boutique",
        "address": "Test Address 123",
        "phone": "+905551234567",
        "email": f"test_hotel_v6_{int(datetime.now().timestamp())}@example.com",
        "password": "TestPass123!"
    }
    
    register_resp = requests.post(f'{backend_url}/auth/register', json=second_hotel_data)
    if register_resp.status_code == 200:
        second_hotel = register_resp.json()
        print(f"✅ Created second hotel: {second_hotel['name']}")
        
        # Login as second hotel
        second_creds = {'username': second_hotel_data['email'], 'password': 'TestPass123!'}
        second_login_resp = requests.post(f'{backend_url}/auth/login', data=second_creds,
                                        headers={'Content-Type': 'application/x-www-form-urlencoded'})
        if second_login_resp.status_code == 200:
            second_token = second_login_resp.json()['access_token']
            second_headers = {'Authorization': f'Bearer {second_token}', 'Content-Type': 'application/json'}
            print("✅ Second hotel authenticated")
        else:
            print("❌ Second hotel login failed")
            return False
    else:
        print(f"❌ Failed to create second hotel: {register_resp.status_code}")
        return False
    
    # 3. Create a listing (as admin hotel)
    future_date_start = datetime.now(timezone.utc) + timedelta(days=30)
    future_date_end = future_date_start + timedelta(days=3)
    
    listing_data = {
        "region": "Sapanca",
        "micro_location": "Göl Kenarı",
        "concept": "Bungalov",
        "capacity_label": "2+1",
        "pax": 3,
        "date_start": future_date_start.isoformat(),
        "date_end": future_date_end.isoformat(),
        "nights": 3,
        "price_min": 1200.0,
        "price_max": 1500.0,
        "availability_status": "available",
        "room_type": "bungalov",
        "breakfast_included": True,
        "notes": "V6 Test Listing for PDF Export",
        "allow_cross_region": False
    }
    
    listing_resp = requests.post(f'{backend_url}/listings', json=listing_data, headers=headers)
    if listing_resp.status_code == 200:
        listing = listing_resp.json()
        print(f"✅ Created listing: {listing['id']}")
    else:
        print(f"❌ Failed to create listing: {listing_resp.status_code}")
        return False
    
    # 4. Create a request (as second hotel)
    request_data = {
        "listing_id": listing['id'],
        "guest_type": "family",
        "notes": "V6 Test Request",
        "confirm_window_minutes": 120
    }
    
    request_resp = requests.post(f'{backend_url}/requests', json=request_data, headers=second_headers)
    if request_resp.status_code == 200:
        request = request_resp.json()
        print(f"✅ Created request: {request['id']}")
    else:
        print(f"❌ Failed to create request: {request_resp.status_code}")
        return False
    
    # 5. Accept the request (as admin hotel) - creates match
    accept_resp = requests.post(f'{backend_url}/requests/{request["id"]}/accept', headers=headers)
    if accept_resp.status_code == 200:
        match = accept_resp.json()
        print(f"✅ Created match: {match['id']} - Reference: {match['reference_code']}")
    else:
        print(f"❌ Failed to accept request: {accept_resp.status_code}")
        return False
    
    # 6. Create payment (as second hotel - the requester pays)
    payment_data = {
        "match_id": match['id'],
        "method": "mock"
    }
    
    payment_resp = requests.post(f'{backend_url}/payments/initiate', json=payment_data, headers=second_headers)
    if payment_resp.status_code == 200:
        payment = payment_resp.json()
        print(f"✅ Created payment: {payment['id']}")
    else:
        print(f"❌ Failed to create payment: {payment_resp.status_code}")
        return False
    
    # 7. Complete payment (generates invoice)
    complete_resp = requests.post(f'{backend_url}/payments/{payment["id"]}/complete', headers=second_headers)
    if complete_resp.status_code == 200:
        print(f"✅ Payment completed successfully")
    else:
        print(f"❌ Failed to complete payment: {complete_resp.status_code}")
        return False
    
    # 8. Test PDF Invoice Export
    invoices_resp = requests.get(f'{backend_url}/invoices', headers=second_headers)
    if invoices_resp.status_code == 200:
        invoices = invoices_resp.json()
        if invoices:
            invoice_id = invoices[0]['id']
            print(f"✅ Found invoice: {invoice_id}")
            
            # Test PDF export
            pdf_resp = requests.get(f'{backend_url}/invoices/{invoice_id}/pdf', headers=second_headers)
            if pdf_resp.status_code == 200:
                content_type = pdf_resp.headers.get('Content-Type', '')
                if 'application/pdf' in content_type:
                    pdf_size = len(pdf_resp.content)
                    print(f"✅ PDF EXPORT SUCCESS: Size {pdf_size} bytes, Content-Type: {content_type}")
                    return True
                else:
                    print(f"❌ PDF Export failed - Wrong content type: {content_type}")
                    return False
            else:
                print(f"❌ PDF Export failed: {pdf_resp.status_code}")
                return False
        else:
            print("❌ No invoices found after payment completion")
            return False
    else:
        print(f"❌ Failed to retrieve invoices: {invoices_resp.status_code}")
        return False

if __name__ == "__main__":
    success = test_complete_flow()
    if success:
        print("\n🎉 COMPLETE V6 TEST FLOW: SUCCESS")
        print("✅ All features working: Listing → Request → Match → Payment → Invoice → PDF Export")
    else:
        print("\n❌ COMPLETE V6 TEST FLOW: FAILED")
        print("Some components in the flow are not working correctly")