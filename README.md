# Vercel Deployment Guide

## Files Structure
```
your-project/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── vercel.json           # Vercel configuration
└── README.md             # This guide
```

## Step 1: Prepare Your Files

1. Save all three files (`app.py`, `requirements.txt`, `vercel.json`) in your project directory
2. Make sure your Discord bot is created and has the required permissions

## Step 2: Set Up Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token (you'll need this for environment variables)
5. Get your Discord channel ID:
   - Enable Developer Mode in Discord
   - Right-click your channel → Copy ID

## Step 3: Bot Permissions

Invite your bot to your server with these permissions:
- Send Messages
- Attach Files
- Read Message History
- View Channel

Permission integer: `117760` (use this in OAuth2 URL generator)

## Step 4: Deploy to Vercel

### Option A: Using Vercel CLI
```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy (from your project directory)
vercel

# Set environment variables
vercel env add DISCORD_BOT_TOKEN
vercel env add CHANNEL_ID

# Redeploy with environment variables
vercel --prod
```

### Option B: Using Vercel Dashboard
1. Go to [vercel.com](https://vercel.com) and login
2. Click "New Project"
3. Import your Git repository or upload files
4. In Settings → Environment Variables, add:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token
   - `CHANNEL_ID`: Your Discord channel ID (as number, not string)

## Step 5: Test Your API

Once deployed, your API will be available at:
- `https://your-project.vercel.app/track-view` - Track views
- `https://your-project.vercel.app/stats` - Get statistics

## Step 6: Update Your Website

Replace `YOUR_FLASK_API_URL` in your website's JavaScript with your Vercel URL:

```javascript
fetch('https://your-project.vercel.app/track-view', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Referer': window.location.href
    }
})
```

## Important Notes

1. **Serverless Functions**: Vercel uses serverless functions, so each request creates a new instance
2. **File Storage**: Temporary files are stored in `/tmp/` directory
3. **Cold Starts**: First request might be slower due to Discord client initialization
4. **Rate Limits**: Be aware of Discord API rate limits

## Environment Variables

- `DISCORD_BOT_TOKEN`: Your Discord bot token (required)
- `CHANNEL_ID`: Discord channel ID where views.json will be stored (required)

## Troubleshooting

1. **Bot Token Issues**: Make sure your bot token is correct and the bot is in your server
2. **Channel ID Issues**: Channel ID should be a number, not a string
3. **Permissions**: Ensure your bot has the required permissions in the channel
4. **Referrer Issues**: The API only accepts requests from `https://tunnelbearsub.mcboss.top/`

## API Response Format

### Success Response (track-view):
```json
{
  "success": true,
  "is_new_visitor": true,
  "total_views": 1,
  "total_unique_visitors": 1
}
```

### Stats Response:
```json
{
  "total_unique_visitors": 1,
  "total_views": 1,
  "data": {
    "192.168.1.1": {
      "first_viewed": "2025-01-01T12:00:00.000000",
      "last_viewed": "2025-01-01T12:00:00.000000",
      "total_views": 1,
      "region": "New York, New York, United States",
      "timezone": "America/New_York",
      "device": "Desktop - Windows - Chrome",
      "user_agent": "Mozilla/5.0..."
    }
  }
}
```