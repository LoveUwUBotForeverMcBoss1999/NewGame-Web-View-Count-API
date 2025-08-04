from flask import Flask, request, jsonify
import discord
import json
import asyncio
import threading
import os
from datetime import datetime
import requests

app = Flask(__name__)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# Global variables
views_data = {}
bot_ready = False
channel = None


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


async def update_views_file():
    """Update the views.json file in Discord"""
    global channel, views_data

    if not channel:
        return False

    try:
        # Create JSON content
        json_content = json.dumps(views_data, indent=2)

        # Check if views.json already exists
        messages = []
        async for message in channel.history(limit=100):
            if message.author == bot.user and message.attachments:
                for attachment in message.attachments:
                    if attachment.filename == 'views.json':
                        await message.delete()
                        break

        # Upload new file
        import io
        file_buffer = io.StringIO(json_content)
        file = discord.File(file_buffer, filename='views.json')
        await channel.send(file=file)
        return True

    except Exception as e:
        print(f"Error updating views file: {e}")
        return False


@bot.event
async def on_ready():
    global bot_ready, channel
    print(f'Bot logged in as {bot.user}')
    bot_ready = True

    # Get channel
    channel_id = int(os.environ.get('CHANNEL_ID'))
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"Channel with ID {channel_id} not found")


def run_bot():
    """Run the Discord bot in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    token = os.environ.get('DISCORD_BOT_TOKEN')
    if not token:
        print("DISCORD_BOT_TOKEN not found")
        return

    try:
        loop.run_until_complete(bot.start(token))
    except Exception as e:
        print(f"Bot error: {e}")


# Start bot in background thread
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()


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

    # Update Discord file asynchronously
    if bot_ready and channel:
        asyncio.run_coroutine_threadsafe(update_views_file(), bot.loop)

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
        'bot_ready': bot_ready,
        'total_unique_ips': len(views_data)
    })


if __name__ == '__main__':
    app.run(debug=True)