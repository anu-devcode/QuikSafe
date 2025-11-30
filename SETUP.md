# QuikSafe Bot - Setup Guide

This guide will help you set up and run QuikSafe Bot.

## Prerequisites

Before you begin, make sure you have:

1. **Python 3.9+** installed
2. **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
3. **Supabase Account** (free tier available at [supabase.com](https://supabase.com))
4. **Google Gemini API Key** (free tier available at [ai.google.dev](https://ai.google.dev))

## Step 1: Get Your API Keys

### Telegram Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Supabase Setup
1. Go to [supabase.com](https://supabase.com) and create a free account
2. Create a new project
3. Go to Project Settings → API
4. Copy your **Project URL** and **anon/public key**
5. Go to SQL Editor and run the schema from `src/database/schema.sql`

### Gemini API Key
1. Go to [ai.google.dev](https://ai.google.dev)
2. Click "Get API Key"
3. Create a new API key (free tier available)
4. Copy the API key

## Step 2: Install Dependencies

```bash
# Navigate to project directory
cd telegram-bot

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   copy .env.example .env
   ```

2. Generate an encryption key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. Edit `.env` file and fill in your credentials:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   GEMINI_API_KEY=your_gemini_api_key_here
   ENCRYPTION_KEY=your_generated_encryption_key
   ```

## Step 4: Set Up Database

1. Open your Supabase project dashboard
2. Go to SQL Editor
3. Copy the contents of `src/database/schema.sql`
4. Paste and run the SQL to create tables

## Step 5: Run the Bot

```bash
# Make sure virtual environment is activated
python src/main.py
```

You should see:
```
INFO - Starting QuikSafe Bot...
INFO - All components initialized successfully
INFO - Bot is starting... Press Ctrl+C to stop
```

## Step 6: Test Your Bot

1. Open Telegram and search for your bot
2. Send `/start` command
3. Create a master password when prompted
4. Try commands like:
   - `/help` - See all commands
   - `/savepassword` - Save a password
   - `/addtask` - Create a task
   - Send a file to save it

## Troubleshooting

### "Configuration error: TELEGRAM_BOT_TOKEN is required"
- Make sure your `.env` file exists and has the correct token

### "Failed to connect to database"
- Check your Supabase URL and key
- Make sure your Supabase project is active

### "Invalid encryption key"
- The encryption key must be exactly 44 characters
- Generate a new one using the command in Step 3

### Bot doesn't respond
- Make sure the bot is running (`python src/main.py`)
- Check that you used the correct bot token
- Verify your internet connection

## Security Best Practices

1. **Never share your `.env` file** - It contains sensitive credentials
2. **Keep your master password secure** - It cannot be recovered if lost
3. **Use a strong master password** - Follow the password requirements
4. **Regularly backup your database** - Use Supabase's backup features
5. **Don't run the bot on public computers** - Keep it on your personal server

## Next Steps

- Read the [README.md](README.md) for feature documentation
- Check out the [database schema](src/database/schema.sql) to understand data structure
- Explore the code to customize the bot for your needs

## Support

If you encounter issues:
1. Check the logs for error messages
2. Verify all environment variables are set correctly
3. Ensure all dependencies are installed
4. Make sure the database schema is created

---

**Note**: This bot uses free tiers of all services (Telegram, Supabase, Gemini). No costs are incurred for normal usage.
