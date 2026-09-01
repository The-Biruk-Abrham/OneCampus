"""
Convenience entrypoint script to run the University Events Hub Telegram Bot.
Usage:
    python run_bot.py
"""
import sys
import socket
from bot.main import main

_lock_socket = None


def acquire_bot_instance_lock(port: int = 48199):
    """
    Guarantees only ONE instance of the bot runs at a time.
    Prevents polling loops from colliding and sending duplicate notifications.
    """
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', port))
    except (socket.error, OSError):
        print("\n" + "=" * 60)
        print("⚠️  WARNING: Another instance of the Telegram bot is already running!")
        print("To avoid duplicate messages and polling conflicts, only one instance is allowed.")
        print("Please terminate any other running bot process first.")
        print("=" * 60 + "\n")
        sys.exit(1)


if __name__ == '__main__':
    acquire_bot_instance_lock()
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot process stopped by user.")
        sys.exit(0)
