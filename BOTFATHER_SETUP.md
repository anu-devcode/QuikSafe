# BotFather Setup Guide

This guide will help you configure your QuikSafe Bot with BotFather to enable the custom commands menu and optimize the bot's appearance.

## Prerequisites

- Your bot must be created via [@BotFather](https://t.me/botfather)
- You need your bot's username (e.g., `@YourQuikSafeBot`)

## Step 1: Set Bot Commands Menu

The commands menu appears when users type `/` in the chat. Configure it with these commands:

1. Open [@BotFather](https://t.me/botfather)
2. Send `/setcommands`
3. Select your bot
4. Paste the following command list:

```
start - Start the bot and show main menu
help - Show help and available commands
savepassword - Save a new password securely
getpassword - Retrieve a saved password
listpasswords - List all saved passwords
deletepassword - Delete a password
addtask - Create a new task
listtasks - View all tasks
completetask - Mark a task as complete
deletetask - Delete a task
listfiles - Browse saved files
getfile - Retrieve a file
deletefile - Delete a file
search - Smart search across all data
summarize - Get AI summary of tasks
cancel - Cancel current operation
```

## Step 2: Set Bot Description

The description appears in the bot's profile.

1. Send `/setdescription` to BotFather
2. Select your bot
3. Paste:

```
🔐 QuikSafe Bot - Your Secure Personal Assistant

Securely manage passwords, tasks, and files with AES-256 encryption. Features:
• Password Management with smart organization
• Task Management with priorities and due dates
• File Storage with intelligent categorization
• AI-Powered Search across all your data
• Smart Auto-Organizer with tag suggestions

All your data is encrypted and secure. Your master password is never stored in plaintext.
```

## Step 3: Set About Text

The about text appears when users first open the bot.

1. Send `/setabouttext` to BotFather
2. Select your bot
3. Paste:

```
QuikSafe Bot helps you securely manage passwords, tasks, and files using military-grade AES-256 encryption. Smart AI features help you stay organized effortlessly.
```

## Step 4: Set Bot Picture (Optional)

Create or use a professional bot profile picture:

1. Send `/setuserpic` to BotFather
2. Select your bot
3. Upload an image (recommended: 512x512px)

**Suggested Design:**
- Icon: 🔐 or a lock/shield symbol
- Colors: Blue and green (security and trust)
- Style: Modern, clean, professional

## Step 5: Enable Inline Mode (Optional)

If you want users to use the bot in other chats:

1. Send `/setinline` to BotFather
2. Select your bot
3. Enable inline mode

## Step 6: Set Inline Feedback

1. Send `/setinlinefeedback` to BotFather
2. Select your bot
3. Choose "Enabled" to get feedback on inline queries

## Deep Links Configuration

Your bot now supports deep links for direct feature access. Share these links with users:

### Quick Action Links

Replace `YourBotUsername` with your actual bot username:

- **Save Password**: `https://t.me/YourBotUsername?start=addpwd`
- **Add Task**: `https://t.me/YourBotUsername?start=addtsk`
- **Upload File**: `https://t.me/YourBotUsername?start=upfile`
- **View Passwords**: `https://t.me/YourBotUsername?start=vpwd`
- **View Tasks**: `https://t.me/YourBotUsername?start=vtsk`
- **View Files**: `https://t.me/YourBotUsername?start=vfile`
- **Search**: `https://t.me/YourBotUsername?start=srch`
- **Settings**: `https://t.me/YourBotUsername?start=sett`

### Example Usage

You can share these links:
- In your website or documentation
- In other Telegram groups/channels
- As quick bookmarks for users

## Testing Your Configuration

After completing the setup:

1. Start a chat with your bot
2. Type `/` to see the commands menu
3. Send `/start` to see the modern main menu with inline keyboards
4. Test a deep link by clicking one of the links above
5. Verify all buttons and navigation work correctly

## Troubleshooting

### Commands menu not showing
- Make sure you completed Step 1 correctly
- Restart your Telegram app
- Try typing `/` again

### Deep links not working
- Verify your bot username is correct (no @ symbol in the URL)
- Make sure the bot is running
- Check that users are authenticated

### Inline keyboards not appearing
- Ensure your bot code is updated with the latest changes
- Check that CallbackQueryHandler is registered in main.py
- Verify no errors in the bot logs

## Additional Recommendations

### Privacy Settings

1. Send `/setjoingroups` to BotFather
2. Select your bot
3. Choose "Disable" if you don't want the bot added to groups

### Group Privacy

1. Send `/setprivacy` to BotFather
2. Select your bot
3. Choose "Disable" for full message access in groups (if needed)

## Support

If you encounter issues:
1. Check the bot logs for errors
2. Verify all environment variables are set correctly
3. Ensure Supabase database is properly configured
4. Test with `/start` command first

---

**Note**: After making changes in BotFather, they may take a few minutes to propagate. If changes don't appear immediately, wait 5-10 minutes and restart your Telegram app.
