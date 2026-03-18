# QuikSafe Bot 🔐

An AI-integrated Telegram bot designed to securely save, organize, and manage passwords, tasks, and files. QuikSafe Bot provides smart organization, easy retrieval, and enhanced security for your personal data.

## Features

### 🔑 Password Management
- Securely store passwords with AES-256 encryption
- Organize passwords by service name and tags
- Quick retrieval with natural language search
- Master password protection

### ✅ Task Management
- Create and organize tasks with priorities
- Set due dates and track completion
- Encrypted storage for privacy
- AI-powered task summarization

### 📁 File Storage
- Save files directly in Telegram
- Organize with descriptions and tags
- Support for images, documents, videos, and more
- Smart search across file metadata

### 🤖 AI-Powered Features
- Natural language search across all data
- Smart content summarization
- Intelligent organization suggestions
- Context-aware retrieval

## Technology Stack

- **Backend**: Python 3.9+ with `python-telegram-bot`
- **Database**: PostgreSQL (Coolify-managed)
- **Storage**: Telegram File IDs
- **AI**: Hugging Face Inference API
- **Security**: AES-256 (Fernet) encryption + Argon2 password hashing

## Prerequisites

- Python 3.9 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- PostgreSQL database (recommended: Coolify PostgreSQL service)
- Hugging Face API Key

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd QuikSafe
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Windows
   copy .env.example .env

   # macOS/Linux
   cp .env.example .env
   ```
   
   Edit `.env` and fill in your credentials:
   - `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
   - `DATABASE_URL` - PostgreSQL connection string
   - `HUGGINGFACE_API_KEY` - Your Hugging Face API key
   - `ENCRYPTION_KEY` - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

5. **Set up database**
   - Schema and migrations are auto-applied on startup when `DB_RUN_MIGRATIONS_ON_STARTUP=true`

6. **Run the bot**
   ```bash
   python src/main.py
   ```

## Usage

### First Time Setup
1. Start a chat with your bot on Telegram
2. Send `/start` to begin
3. Create a master password when prompted
4. You're ready to use QuikSafe Bot!

### Commands

#### Password Management
- `/savepassword` - Save a new password
- `/getpassword <service>` - Retrieve a password
- `/listpasswords` - List all saved passwords
- `/deletepassword <service>` - Delete a password

#### Task Management
- `/addtask <task>` - Create a new task
- `/listtasks` - View all tasks
- `/completetask <id>` - Mark task as complete
- `/deletetask <id>` - Delete a task

#### File Management
- Send any file to save it
- `/listfiles` - List all saved files
- `/getfile <name>` - Retrieve a file
- `/deletefile <id>` - Delete a file

#### AI Features
- `/search <query>` - Smart search across all data
- `/summarize` - Get AI summary of your tasks

## Security Features

- **End-to-end encryption**: All sensitive data encrypted with AES-256
- **Master password**: Hashed with Argon2 (never stored in plaintext)
- **Secure key management**: Encryption keys stored in environment variables
- **No plaintext storage**: Passwords, tasks, and sensitive file metadata always encrypted
- **Session management**: Secure user authentication and session handling

## Project Structure

```
QuikSafe/
├── src/
│   ├── main.py                 # Bot entry point
│   ├── config.py               # Configuration management
│   ├── database/
│   │   ├── db_manager.py       # Database operations
│   │   ├── schema.sql          # Database schema
│   │   ├── rls_policies.sql    # Optional PostgreSQL RLS template
│   │   └── migrations/         # SQL migrations
│   ├── security/
│   │   ├── encryption.py       # Encryption utilities
│   │   └── auth.py             # Authentication
│   ├── handlers/
│   │   ├── start_handler.py    # Welcome & registration
│   │   ├── password_handler.py # Password management
│   │   ├── task_handler.py     # Task management
│   │   ├── file_handler.py     # File storage
│   │   └── search_handler.py   # AI search
│   ├── ai/
│   │   └── huggingface_client.py # Hugging Face AI integration
│   └── utils/
│       ├── validators.py       # Input validation
│       └── formatters.py       # Message formatting
├── run.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use this project for personal or commercial purposes.

## Support

If you encounter any issues or have questions, please open an issue on GitHub.

## Deployment

For production deployment on a DigitalOcean VM using Coolify, follow [DEPLOY_COOLIFY.md](DEPLOY_COOLIFY.md).

---

**⚠️ Security Notice**: Never share your `.env` file or encryption keys. Keep your master password secure and memorable - it cannot be recovered if lost.
