#!/usr/bin/env python3
"""
Profile API Setup and Run Script

This script initializes and starts the Profile & Engagement API server
with proper configuration and environment setup.
"""

import os
import sys
import subprocess
from pathlib import Path


def setup_environment():
    """Set up environment variables and configuration"""
    print("Setting up Profile API environment...")

    # Set the API key - this is the default key used by the test harness
    api_key = os.getenv("API_KEY", "dev-api-key-12345")
    os.environ["API_KEY"] = api_key

    print(f"API Key configured: {api_key}")

    # Use SQLite for development to avoid PostgreSQL dependency
    db_url = os.getenv("DATABASE_URL", "sqlite:///./profile_api.db")
    os.environ["DATABASE_URL"] = db_url

    print(f"Database URL: {db_url}")

    # Set other environment variables if needed
    os.environ.setdefault("PYTHONPATH", str(Path.cwd()))

    return True


def check_dependencies():
    """Check if required dependencies are installed"""
    print("Checking dependencies...")

    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("Warning: requirements.txt not found")
        return True

    try:
        # Check if we can import the main dependencies
        import fastapi
        import uvicorn

        print("Core dependencies found")
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Installing dependencies...")

        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
            )
            print("Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("Failed to install dependencies")
            return False


def start_server():
    """Start the Profile API server"""
    print("Starting Profile & Engagement API server...")
    print("Server will be available at: http://localhost:8002")
    print("Health check endpoint: http://localhost:8002/health")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)

    try:
        import uvicorn

        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8002,
            reload=True,
            log_level="info",
            access_log=True,
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


def main():
    """Main setup and run function"""
    print("Profile & Engagement API - Setup and Run")
    print("=" * 40)

    # Change to the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}")

    # Setup environment
    if not setup_environment():
        print("Failed to setup environment")
        sys.exit(1)

    # Check dependencies
    if not check_dependencies():
        print("Failed to check/install dependencies")
        sys.exit(1)

    # Start the server
    start_server()


if __name__ == "__main__":
    main()
