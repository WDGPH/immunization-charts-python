#!/usr/bin/env python3
"""
Launcher script for the Streamlit web interface.

This script provides an easy way to start the web interface without
installing the package in development mode.
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Launch the Streamlit web interface."""
    # Get the project root directory
    project_root = Path(__file__).parent
    src_path = project_root / "src"
    
    # Add src to Python path
    sys.path.insert(0, str(src_path))
    
    # Set the Streamlit app path
    app_path = src_path / "immunization_charts" / "web" / "streamlit_app.py"
    
    # Launch Streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run", 
        str(app_path),
        "--server.port", "8501",
        "--server.address", "localhost"
    ]
    
    print("🚀 Starting Immunization Charts Web Interface...")
    print(f"📁 App path: {app_path}")
    print("🌐 Open your browser to: http://localhost:8501")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        subprocess.run(cmd, cwd=project_root)
    except KeyboardInterrupt:
        print("\n👋 Web interface stopped. Goodbye!")

if __name__ == "__main__":
    main()
