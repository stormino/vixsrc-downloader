#!/bin/bash
#
# VixSrc Downloader - Installation Script
#
# This script installs all dependencies needed for the VixSrc downloader

set -e

echo "=== VixSrc Downloader Installation ==="
echo ""

# Check Python version
echo "[*] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "[+] Found Python $PYTHON_VERSION"

# Install Python dependencies
echo ""
echo "[*] Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages || \
    pip install -r requirements.txt --user || \
    pip3 install -r requirements.txt

# Check for downloaders
echo ""
echo "[*] Checking for video downloaders..."

HAS_YTDLP=false
HAS_FFMPEG=false

if command -v yt-dlp &> /dev/null; then
    echo "[+] yt-dlp is installed"
    HAS_YTDLP=true
else
    echo "[!] yt-dlp is not installed"
fi

if command -v ffmpeg &> /dev/null; then
    echo "[+] ffmpeg is installed"
    HAS_FFMPEG=true
else
    echo "[!] ffmpeg is not installed"
fi

# Install downloader if needed
if [ "$HAS_YTDLP" = false ] && [ "$HAS_FFMPEG" = false ]; then
    echo ""
    echo "[*] No downloader found. Installing yt-dlp..."
    pip install yt-dlp --break-system-packages || \
        pip install yt-dlp --user || \
        pip3 install yt-dlp
    
    if command -v yt-dlp &> /dev/null; then
        echo "[+] yt-dlp installed successfully"
    else
        echo "[!] Warning: yt-dlp installation may have failed"
        echo "[!] You may need to install ffmpeg manually:"
        echo "    Ubuntu/Debian: sudo apt-get install ffmpeg"
        echo "    CentOS/RHEL:   sudo yum install ffmpeg"
        echo "    macOS:         brew install ffmpeg"
    fi
fi

# Make script executable
echo ""
echo "[*] Making script executable..."
chmod +x vixsrc_downloader.py

echo ""
echo "[+] Installation complete!"
echo ""
echo "Optional: Set up TMDB API key for enhanced filenames"
echo "  1. Get a free API key at: https://www.themoviedb.org/settings/api"
echo "  2. Set it as an environment variable:"
echo "     export TMDB_API_KEY=\"your_api_key_here\""
echo "  3. Add to ~/.bashrc or ~/.zshrc for persistence"
echo ""
echo "Usage examples:"
echo "  ./vixsrc_downloader.py --movie 550  # Auto-generates: Fight.Club.1999.mp4"
echo "  ./vixsrc_downloader.py --tv 60625 --season 4 --episode 4  # Auto-generates: Breaking.Bad.S04E04.Ozymandias.mp4"
echo "  ./vixsrc_downloader.py --movie 550 --output fight_club.mp4  # Custom filename"
echo "  ./vixsrc_downloader.py --help"
echo ""
echo "For batch downloads:"
echo "  # See example_batch.txt for format"
echo "  ./vixsrc_downloader.py --batch downloads.txt --output-dir ./videos"
echo "  ./vixsrc_downloader.py --batch downloads.txt --parallel 3  # 3 parallel downloads"
