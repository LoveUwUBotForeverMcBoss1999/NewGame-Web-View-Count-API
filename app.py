from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# In-memory storage (will reset on each cold start)
views_data = {}


def get_ip_info(ip):
    """Get IP location info"""
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
        data = response.json()
        if data['status'] == 'success':
            return f"{data.get('city', 'Unknown')}, {data.get('country', 'Unknown')}"
    except:
        pass
    return "Unknown"


def get_device_info(user_agent):
    """Extract device info from user agent"""
    if not user_agent:
        return "Unknown"

    user_agent = user_agent.lower()
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        return "Mobile"
    elif 'tablet' in user_agent or 'ipad' in user_agent:
        return "Tablet"
    else:
        return "Desktop"


def send_to_discord():
    """Send views data to Discord using webhook"""
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not found")
        return False

    try:
        # Create JSON content
        json_content = json.dumps(views_data, indent=2)

        # Send as a file attachment
        files = {
            'file': ('views.json', json_content, 'application/json')
        }

        data = {
            'content': f'📊 **View Stats Updated** - Total unique IPs: {len(views_data)}'
        }

        response = requests.post(webhook_url, data=data, files=files, timeout=10)
        return response.status_code == 200

    except Exception as e:
        print(f"Error sending to Discord: {e}")
        return False


@app.route('/', methods=['GET'])
def track_view():
    """Track page views and update Discord file"""
    global views_data

    # Check if request is from allowed origin
    referer = request.headers.get('Referer', '')
    if not referer.startswith('https://tunsub.mcboss.top/'):
        return jsonify({'error': 'Unauthorized origin'}), 403

    # Get client info
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()

    user_agent = request.headers.get('User-Agent', '')
    current_time = datetime.now().isoformat()

    # Get location and device info
    region = get_ip_info(client_ip)
    device = get_device_info(user_agent)

    # Track if this is a new IP
    is_new_ip = client_ip not in views_data

    # Check if IP already exists
    if client_ip in views_data:
        # Update existing IP data
        views_data[client_ip]['total_views'] += 1
        views_data[client_ip]['last_viewed'] = current_time
    else:
        # New IP
        views_data[client_ip] = {
            'first_viewed': current_time,
            'last_viewed': current_time,
            'total_views': 1,
            'region': region,
            'device': device
        }

    # Send to Discord (only for new IPs to avoid spam)
    if is_new_ip:
        send_to_discord()

    return jsonify({
        'status': 'success',
        'ip': client_ip,
        'total_views': views_data[client_ip]['total_views'],
        'first_viewed': views_data[client_ip]['first_viewed']
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'total_unique_ips': len(views_data)
    })


# For local testing
if __name__ == '__main__':
    app.run(debug=True)

# For local testing
if __name__ == '__main__':
    app.run(debug=True)