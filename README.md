# Tetris Battle — 雙人連線對戰

A two-player online Tetris battle game built with WebSocket (Python backend) and Canvas (vanilla HTML/JS frontend). Two players connect to the same room and compete — clearing lines sends garbage blocks to the opponent's board.

## Architecture

```
┌──────────────┐    WebSocket     ┌──────────────┐
│  Browser A   │◄────────────────►│  Python       │
│  (index.html)│    ws://:8765    │  Server       │
│              │                  │  (server.py)  │
│  Canvas +    │    WebSocket     │  ┌──────────┐ │
│  DAS/ARR     │◄────────────────►│  │ game.py  │ │
│  Controls    │                  │  │ Board    │ │
└──────────────┘                  │  │ Logic    │ │
                                  │  └──────────┘ │
┌──────────────┐    WebSocket     │  Room Manager │
│  Browser B   │◄────────────────►│  Heartbeat    │
│  (index.html)│    ws://:8765    │  Game Loop    │
└──────────────┘                  └──────────────┘
```

## Quick Start (Development)

### Prerequisites
- Python 3.10+
- `pip install websockets`

### Run
```bash
# Install dependency
pip install websockets

# Start server
python server.py

# Open http://localhost:8765 in two browser tabs
# Player 1: Click "Create Room", note room code
# Player 2: Enter room code, click "Join"
# Both click "Ready" to start!
```

The server serves `index.html` directly — open your browser to `http://localhost:8765` to play.

### Controls
| Key | Action |
|-----|--------|
| ← → | Move left/right |
| ↓ | Soft drop |
| ↑ | Rotate |
| Space | Hard drop |
| C / Shift | Hold piece |

DAS (Delayed Auto Shift): 167ms delay → 33ms repeat interval for left/right/down.

## Docker

```bash
# Build and run
docker build -t tetris-battle .
docker run -p 8765:8765 tetris-battle

# Or using docker compose (recommended for multi-platform)
docker compose up --build
```

Open `http://localhost:8765` and start a game.

## Game Features

- 7 standard Tetris pieces (I, O, T, S, Z, J, L) with SRS rotation + wall kicks
- 7-bag randomizer (no long droughts)
- Hold piece with swap-once-per-drop
- Hard drop with instant lock
- Line clear scoring: 100/300/500/800 × level
- Garbage attack: 0/1/2/4 lines for 1/2/3/4 clears
- 20Hz state sync (50ms game loop)
- Heartbeat timeout (5s interval, 2-miss disconnect)
- Auto-reconnect with exponential backoff (up to 30s, 10 attempts)
- Touch controls for mobile devices

## Project Structure

```
├── server.py      # WebSocket server (room mgmt, game loop, state sync)
├── game.py        # Tetris game logic (Board class, SRS, scoring)
├── index.html     # Frontend (Canvas, DAS/ARR keyboard, touch controls)
├── Dockerfile     # Container image
├── nginx.conf     # nginx config (for docker-compose frontend)
└── README.md      # This file
```

## Testing

```bash
# Run unit tests
python -c "from game import Board; print('game.py imports OK')"

# Run integration test (requires server running)
python test_integration.py
```
