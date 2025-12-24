FROM python:3.13-slim

WORKDIR /app

# Install ffmpeg which is required for yt-dlp to convert HLS streams
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application script
COPY vixsrc_downloader.py .

# Create a directory for downloads
RUN mkdir -p /downloads

# Set the downloads directory as the working directory for output
WORKDIR /downloads

# Set environment variable (can be overridden at runtime)
ENV TMDB_API_KEY=""

# The script is executable
ENTRYPOINT ["python3", "/app/vixsrc_downloader.py"]

# Default command shows help
CMD ["--help"]
