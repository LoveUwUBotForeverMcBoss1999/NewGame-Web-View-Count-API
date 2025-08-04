from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime
import io

app = Flask(__name__)
CORS(app, origins=["https://tunsub.mcboss.top"])

# In-memory storage
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


def update_discord_file():
    """Update views.json file in Discord using Discord API"""
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    channel_id = os.environ.get('CHANNEL_ID')

    if not bot_token or not channel_id:
        print("Missing DISCORD_BOT_TOKEN or CHANNEL_ID")
        return False

    try:
        headers = {
            'Authorization': f'Bot {bot_token}',
            'Content-Type': 'application/json'
        }

        # Step 1: Get recent messages to find and delete old views.json
        messages_url = f'https://discord.com/api/v10/channels/{channel_id}/messages?limit=50'
        response = requests.get(messages_url, headers=headers, timeout=10)

        if response.status_code == 200:
            messages = response.json()
            # Delete old views.json files
            for message in messages:
                if message.get('attachments'):
                    for attachment in message['attachments']:
                        if attachment['filename'] == 'views.json':
                            delete_url = f'https://discord.com/api/v10/channels/{channel_id}/messages/{message["id"]}'
                            requests.delete(delete_url, headers=headers, timeout=10)
                            break

        # Step 2: Upload new views.json file
        json_content = json.dumps(views_data, indent=2)

        files = {
            'file': ('views.json', json_content, 'application/json')
        }

        payload = {
            'content': f'📊 **Views Updated** - Total unique IPs: {len(views_data)}'
        }

        # Remove Content-Type for multipart
        upload_headers = {
            'Authorization': f'Bot {bot_token}'
        }

        upload_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        response = requests.post(upload_url, headers=upload_headers, data=payload, files=files, timeout=15)

        if response.status_code == 200:
            print("Successfully updated views.json in Discord")
            return True
        else:
            print(f"Failed to upload file: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error updating Discord file: {e}")
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

    # Update or create IP entry
    if client_ip in views_data:
        # Existing IP - update view count and last viewed
        views_data[client_ip]['total_views'] += 1
        views_data[client_ip]['last_viewed'] = current_time
    else:
        # New IP - create new entry
        views_data[client_ip] = {
            'first_viewed': current_time,
            'last_viewed': current_time,
            'total_views': 1,
            'region': region,
            'device': device
        }

    # Update Discord file EVERY TIME (both new and existing IPs)
    discord_success = update_discord_file()

    return jsonify({
        'status': 'success',
        'ip': client_ip,
        'total_views': views_data[client_ip]['total_views'],
        'first_viewed': views_data[client_ip]['first_viewed'],
        'is_new_visitor': is_new_ip,
        'discord_updated': discord_success
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