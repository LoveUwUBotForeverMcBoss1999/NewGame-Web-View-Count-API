import json
import os
import requests
import aiohttp
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Get environment variables
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', 0))
ALLOWED_REFERRER = "https://tunnelbearsub.mcboss.top/"
VIEWS_FILE = "views.json"


class DiscordAPI:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.base_url = "https://discord.com/api/v10"
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json"
        }

    async def get_channel_messages(self, limit=50):
        """Get recent messages from channel"""
        url = f"{self.base_url}/channels/{self.channel_id}/messages"
        params = {"limit": limit}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                return []

    async def delete_message(self, message_id):
        """Delete a message"""
        url = f"{self.base_url}/channels/{self.channel_id}/messages/{message_id}"

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=self.headers) as response:
                return response.status == 204

    async def send_file(self, content, file_data, filename):
        """Send a file to Discord channel"""
        url = f"{self.base_url}/channels/{self.channel_id}/messages"

        data = aiohttp.FormData()
        data.add_field('content', content)
        data.add_field('files[0]', file_data, filename=filename, content_type='application/json')

        headers = {"Authorization": f"Bot {self.token}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                return response.status == 200


class ViewTracker:
    def __init__(self):
        self.discord = DiscordAPI(DISCORD_BOT_TOKEN, CHANNEL_ID)
        self.views_data = {}

    async def load_views_from_discord(self):
        """Load existing views data from Discord channel"""
        try:
            messages = await self.discord.get_channel_messages()

            for message in messages:
                if message.get('attachments'):
                    for attachment in message['attachments']:
                        if attachment['filename'] == VIEWS_FILE:
                            # Download the file
                            async with aiohttp.ClientSession() as session:
                                async with session.get(attachment['url']) as response:
                                    if response.status == 200:
                                        file_content = await response.text()
                                        self.views_data = json.loads(file_content)
                                        return

            # If no file found, initialize empty data
            self.views_data = {}

        except Exception as e:
            print(f"Error loading views from Discord: {e}")
            self.views_data = {}

    async def save_views_to_discord(self):
        """Save views data to Discord channel"""
        try:
            # Load current messages to find old views.json
            messages = await self.discord.get_channel_messages()

            # Delete old views.json messages
            for message in messages:
                if message.get('attachments'):
                    for attachment in message['attachments']:
                        if attachment['filename'] == VIEWS_FILE:
                            await self.discord.delete_message(message['id'])
                            break

            # Create new file content
            json_content = json.dumps(self.views_data, indent=2)

            # Create message content
            total_unique = len(self.views_data)
            total_views = sum(data["total_views"] for data in self.views_data.values())

            content = (f"📊 **View Statistics Updated**\n"
                       f"Total unique IPs: {total_unique}\n"
                       f"Total views: {total_views}\n"
                       f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

            # Send new file
            await self.discord.send_file(content, json_content.encode(), VIEWS_FILE)

        except Exception as e:
            print(f"Error saving views to Discord: {e}")

    def get_ip_info(self, ip):
        """Get location info for IP"""
        try:
            response = requests.get(f"http://ipapi.co/{ip}/json/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "country": data.get("country_name", "Unknown"),
                    "region": data.get("region", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "timezone": data.get("timezone", "Unknown")
                }
        except:
            pass

        return {
            "country": "Unknown",
            "region": "Unknown",
            "city": "Unknown",
            "timezone": "Unknown"
        }

    def get_device_info(self, user_agent):
        """Parse user agent for device info"""
        ua = user_agent.lower()

        # Detect OS
        if 'windows' in ua:
            os_name = 'Windows'
        elif 'mac' in ua:
            os_name = 'macOS'
        elif 'linux' in ua:
            os_name = 'Linux'
        elif 'android' in ua:
            os_name = 'Android'
        elif 'iphone' in ua or 'ipad' in ua:
            os_name = 'iOS'
        else:
            os_name = 'Unknown'

        # Detect Browser
        if 'chrome' in ua and 'edg' not in ua:
            browser = 'Chrome'
        elif 'firefox' in ua:
            browser = 'Firefox'
        elif 'safari' in ua and 'chrome' not in ua:
            browser = 'Safari'
        elif 'edg' in ua:
            browser = 'Edge'
        else:
            browser = 'Unknown'

        # Detect device type
        if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
            device_type = 'Mobile'
        elif 'tablet' in ua or 'ipad' in ua:
            device_type = 'Tablet'
        else:
            device_type = 'Desktop'

        return f"{device_type} - {os_name} - {browser}"


# Global tracker instance
tracker = ViewTracker()


@app.route('/track-view', methods=['GET', 'POST'])
def track_view():
    try:
        # Check if required env vars are set
        if not DISCORD_BOT_TOKEN or not CHANNEL_ID:
            return jsonify({"error": "Discord configuration missing"}), 500

        # Check referrer
        referrer = request.headers.get('Referer', '')
        if not referrer.startswith(ALLOWED_REFERRER):
            return jsonify({"error": "Unauthorized referrer"}), 403

        # Get client IP
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        user_agent = request.headers.get('User-Agent', '')
        current_time = datetime.now().isoformat()

        # Run async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def process_view():
            # Load existing data
            await tracker.load_views_from_discord()

            # Get IP and device info
            ip_info = tracker.get_ip_info(client_ip)
            device_info = tracker.get_device_info(user_agent)

            # Check if IP exists
            if client_ip in tracker.views_data:
                # IP exists - increment view count and update last viewed
                tracker.views_data[client_ip]["total_views"] += 1
                tracker.views_data[client_ip]["last_viewed"] = current_time
                is_new_visitor = False
            else:
                # New IP - create new entry
                tracker.views_data[client_ip] = {
                    "first_viewed": current_time,
                    "last_viewed": current_time,
                    "total_views": 1,
                    "region": f"{ip_info['city']}, {ip_info['region']}, {ip_info['country']}",
                    "timezone": ip_info['timezone'],
                    "device": device_info,
                    "user_agent": user_agent
                }
                is_new_visitor = True

            # Save to Discord
            await tracker.save_views_to_discord()

            return {
                "success": True,
                "is_new_visitor": is_new_visitor,
                "total_views": tracker.views_data[client_ip]["total_views"],
                "total_unique_visitors": len(tracker.views_data)
            }

        result = loop.run_until_complete(process_view())
        loop.close()

        return jsonify(result)

    except Exception as e:
        print(f"Error in track_view: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get current statistics"""
    try:
        if not DISCORD_BOT_TOKEN or not CHANNEL_ID:
            return jsonify({"error": "Discord configuration missing"}), 500

        # Load current data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def get_current_stats():
            await tracker.load_views_from_discord()
            total_unique = len(tracker.views_data)
            total_views = sum(data["total_views"] for data in tracker.views_data.values())

            return {
                "total_unique_visitors": total_unique,
                "total_views": total_views,
                "data": tracker.views_data
            }

        result = loop.run_until_complete(get_current_stats())
        loop.close()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return jsonify({"message": "View Tracker API is running"})


# Vercel serverless handler
def handler(request):
    return app(request.environ, lambda *args: None)


if __name__ == '__main__':
    app.run(debug=True)
