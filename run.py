#!/usr/bin/env python3
"""
Acoustic Fella - Room Acoustics Treatment Software
Run this script to start the web application.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from acoustic_fella.web.app import app

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   🎛️  ACOUSTIC FELLA                                      ║
    ║   Room Acoustics Treatment Software                       ║
    ║                                                           ║
    ║   Starting web server...                                  ║
    ║   Open http://localhost:5000 in your browser              ║
    ║                                                           ║
    ║   Press Ctrl+C to stop the server                         ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
