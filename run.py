"""
QuikSafe Bot - Entry Point
Run this file to start the bot: python run.py
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main function
from src.main import main

if __name__ == '__main__':
    main()
