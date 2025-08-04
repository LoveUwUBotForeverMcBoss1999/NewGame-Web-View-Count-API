from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import requests
from datetime import datetime
import hashlib
from collections import defaultdict

app = Flask(__name__)
CORS(app)

# In-memory storage (would use database in production)
views_data = {
    'total_views': 0,
    'unique_visitors': set(),
    'visits': []
}


def get_client_ip():
    """Get the real client IP address"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def get_location_info(ip):
    """Get location information from IP (using free ipapi service)"""
    try:
        if ip in ['127.0.0.1', 'localhost'] or ip.startswith('192.168.'):
            return {'country': 'Local', 'city': 'Local', 'timezone': 'Local'}

        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                'country': data.get('country', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'timezone': data.get('timezone', 'Unknown')
            }
    except:
        pass

    return {'country': 'Unknown', 'city': 'Unknown', 'timezone': 'Unknown'}


def create_visitor_hash(ip, user_agent):
    """Create a hash to identify unique visitors"""
    combined = f"{ip}:{user_agent}"
    return hashlib.md5(combined.encode()).hexdigest()


def send_discord_notification(view_data):
    """Send view data to Discord channel"""
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    channel_id = os.getenv('CHANNEL_ID')

    if not bot_token or not channel_id:
        return False

    # Create embed for Discord
    embed = {
        "title": "🔍 New Page View",
        "color": 0x00ff00,
        "fields": [
            {"name": "📄 Page", "value": view_data['page'], "inline": True},
            {"name": "🌍 Location", "value": f"{view_data['location']['city']}, {view_data['location']['country']}",
             "inline": True},
            {"name": "⏰ Time", "value": view_data['timestamp'], "inline": True},
            {"name": "🖥️ User Agent",
             "value": view_data['user_agent'][:100] + "..." if len(view_data['user_agent']) > 100 else view_data[
                 'user_agent'], "inline": False},
            {"name": "🆔 Visitor ID", "value": view_data['visitor_hash'][:8], "inline": True},
            {"name": "📊 Total Views", "value": str(views_data['total_views']), "inline": True}
        ],
        "timestamp": datetime.utcnow().isoformat()
    }

    payload = {
        "embeds": [embed]
    }

    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            json=payload,
            headers=headers,
            timeout=5
        )
        return response.status_code == 200
    except:
        return False


@app.route('/track-view', methods=['POST', 'GET'])
def track_view():
    """Track a page view"""
    try:
        # Get data from request
        if request.method == 'POST':
            data = request.get_json() or {}
        else:
            data = request.args.to_dict()

        # Get metadata
        ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', 'Unknown')
        referrer = request.headers.get('Referer', 'Direct')
        page = data.get('page', request.headers.get('Referer', 'Unknown'))

        # Create visitor hash
        visitor_hash = create_visitor_hash(ip, user_agent)

        # Get location info
        location = get_location_info(ip)

        # Increment total views
        views_data['total_views'] += 1
        views_data['unique_visitors'].add(visitor_hash)

        # Create view record
        view_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'ip': ip,
            'user_agent': user_agent,
            'referrer': referrer,
            'page': page,
            'visitor_hash': visitor_hash,
            'location': location
        }

        # Store the visit
        views_data['visits'].append(view_record)

        # Keep only last 1000 visits to prevent memory issues
        if len(views_data['visits']) > 1000:
            views_data['visits'] = views_data['visits'][-1000:]

        # Send to Discord
        discord_sent = send_discord_notification(view_record)

        return jsonify({
            'success': True,
            'message': 'View tracked successfully',
            'data': {
                'total_views': views_data['total_views'],
                'unique_visitors': len(views_data['unique_visitors']),
                'discord_logged': discord_sent,
                'visitor_hash': visitor_hash[:8]  # Only show first 8 chars
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error tracking view: {str(e)}'
        }), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get analytics stats"""
    try:
        # Calculate stats
        total_views = views_data['total_views']
        unique_visitors = len(views_data['unique_visitors'])

        # Page stats
        page_stats = defaultdict(int)
        location_stats = defaultdict(int)
        recent_visits = []

        for visit in views_data['visits']:
            page_stats[visit['page']] += 1
            location_key = f"{visit['location']['city']}, {visit['location']['country']}"
            location_stats[location_key] += 1

            # Add to recent visits (limit to last 50)
            if len(recent_visits) < 50:
                recent_visits.append({
                    'timestamp': visit['timestamp'],
                    'page': visit['page'],
                    'location': f"{visit['location']['city']}, {visit['location']['country']}",
                    'visitor_id': visit['visitor_hash'][:8]
                })

        # Sort by count
        top_pages = sorted(page_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        top_locations = sorted(location_stats.items(), key=lambda x: x[1], reverse=True)[:10]

        return jsonify({
            'success': True,
            'stats': {
                'total_views': total_views,
                'unique_visitors': unique_visitors,
                'top_pages': [{'page': page, 'views': count} for page, count in top_pages],
                'top_locations': [{'location': loc, 'views': count} for loc, count in top_locations],
                'recent_visits': list(reversed(recent_visits))  # Most recent first
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting stats: {str(e)}'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'message': 'View Tracker API is running',
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/', methods=['GET'])
def home():
    """API documentation"""
    return jsonify({
        'name': 'View Tracker API',
        'version': '1.0.0',
        'endpoints': {
            '/track-view': 'POST/GET - Track a page view',
            '/stats': 'GET - Get analytics statistics',
            '/health': 'GET - Health check'
        },
        'features': [
            'Discord integration',
            'Unique visitor tracking',
            'Location detection',
            'Real-time analytics'
        ]
    })


# For Vercel
if __name__ == '__main__':
    app.run(debug=True)