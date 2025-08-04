import json
import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import discord
import asyncio

app = Flask(__name__)

# Configuration
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "123456789012345678"))
ALLOWED_REFERRER = "https://tunnelbearsub.mcboss.top/"
VIEWS_FILE = "views.json"

# Discord client setup (using Client instead of Bot for serverless)
intents = discord.Intents.default()
intents.message_content = True


class ViewTracker:
    def __init__(self):
        self.views_data = {}

    async def get_discord_client(self):
        """Create and return authenticated Discord client"""
        client = discord.Client(intents=intents)
        await client.login(DISCORD_BOT_TOKEN)
        return client

    async def load_views_from_discord(self):
        """Load existing views data from Discord channel"""
        client = None
        try:
            client = await self.get_discord_client()
            channel = client.get_channel(CHANNEL_ID)

            # Look for existing views.json file in channel
            async for message in channel.history(limit=100):
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.filename == VIEWS_FILE:
                            # Download and parse the file
                            file_content = await attachment.read()
                            self.views_data = json.loads(file_content.decode('utf-8'))
                            return

            # If no file found, initialize empty data
            self.views_data = {}

        except Exception as e:
            print(f"Error loading views from Discord: {e}")
            self.views_data = {}
        finally:
            if client:
                await client.close()

    async def save_views_to_discord(self):
        """Save views data to Discord channel"""
        client = None
        try:
            client = await self.get_discord_client()
            channel = client.get_channel(CHANNEL_ID)

            # Create JSON file content
            json_content = json.dumps(self.views_data, indent=2)

            # Save to temporary file in /tmp (Vercel's writable directory)
            temp_file_path = f"/tmp/{VIEWS_FILE}"
            with open(temp_file_path, 'w') as f:
                f.write(json_content)

            # Delete old views.json messages
            async for message in channel.history(limit=50):
                if message.author == client.user and message.attachments:
                    for attachment in message.attachments:
                        if attachment.filename == VIEWS_FILE:
                            await message.delete()
                            break

            # Upload new file
            with open(temp_file_path, 'rb') as f:
                await channel.send(
                    content=f"📊 **View Statistics Updated**\n"
                            f"Total unique IPs: {len(self.views_data)}\n"
                            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    file=discord.File(f, VIEWS_FILE)
                )

            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

        except Exception as e:
            print(f"Error saving views to Discord: {e}")
        finally:
            if client:
                await client.close()

    def get_ip_info(self, ip):
        """Get location and device info for IP"""
        try:
            # Get location info from ipapi.co
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
    """Track view endpoint - runs async operations"""
    try:
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

        try:
            # Load existing data
            loop.run_until_complete(tracker.load_views_from_discord())

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
            loop.run_until_complete(tracker.save_views_to_discord())

            return jsonify({
                "success": True,
                "is_new_visitor": is_new_visitor,
                "total_views": tracker.views_data[client_ip]["total_views"],
                "total_unique_visitors": len(tracker.views_data)
            })

        finally:
            loop.close()

    except Exception as e:
        print(f"Error in track_view: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get current statistics"""
    try:
        # Load current data from Discord
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(tracker.load_views_from_discord())

            total_unique = len(tracker.views_data)
            total_views = sum(data["total_views"] for data in tracker.views_data.values())

            return jsonify({
                "total_unique_visitors": total_unique,
                "total_views": total_views,
                "data": tracker.views_data
            })
        finally:
            loop.close()

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Vercel serverless function handler
def handler(request):
    return app(request.environ, start_response)


if __name__ == '__main__':
    app.run(debug=True)