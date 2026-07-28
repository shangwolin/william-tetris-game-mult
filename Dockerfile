FROM python:3.11-slim

WORKDIR /app

# Install websockets library
RUN pip install --no-cache-dir websockets

# Copy all game files
COPY server.py game.py index.html ./

# Expose WebSocket port (open index.html in browser on host)
# For Docker: open http://localhost:8765/ for the game
EXPOSE 8765

CMD ["python", "server.py"]
