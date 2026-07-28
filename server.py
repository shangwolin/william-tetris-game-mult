#!/usr/bin/env python3
"""server.py — Tetris Battle WebSocket Server

Asyncio-based WebSocket server using the `websockets` library.
Manages rooms, game state, heartbeat, and client communication.
"""

import asyncio
import json
import logging
import random
import string
import time
from typing import Dict, Optional, Any

import websockets
from websockets import Response, Headers

from game import Board, PIECES, PIECE_SHAPES, PIECE_INDEX

# ── Logging Setup ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tetris-server")

# ── Constants ──────────────────────────────────────────────────────────────────

HOST = "0.0.0.0"
PORT = 8765
HEARTBEAT_INTERVAL = 5  # seconds

# ── Room Management ────────────────────────────────────────────────────────────


class PlayerConnection:
    """Represents a connected player with their WebSocket and game state."""

    def __init__(self, websocket, player_id: int):
        self.websocket = websocket
        self.player_id = player_id
        self.board: Optional[Board] = None
        self.ready = False
        self.alive = True
        self.last_heartbeat = time.time()
        self.last_tick_time = time.time()
        self.input_queue: asyncio.Queue = asyncio.Queue()


class Room:
    """Manages a single game room with two players."""

    def __init__(self, room_id: str):
        self.room_id = room_id
        self.players: Dict[int, PlayerConnection] = {}
        self.seed: Optional[int] = None
        self.game_started = False
        self.game_over = False
        self.game_task: Optional[asyncio.Task] = None
        self.rematch_votes: set = set()

    @property
    def is_full(self) -> bool:
        return len(self.players) >= 2

    @property
    def is_empty(self) -> bool:
        return len(self.players) == 0

    def add_player(self, websocket) -> int:
        """Add a player to the room. Returns the player ID (1 or 2)."""
        if len(self.players) >= 2:
            raise ValueError("Room is full")

        if 1 not in self.players:
            player_id = 1
        else:
            player_id = 2

        self.players[player_id] = PlayerConnection(websocket, player_id)
        logger.info(f"Player {player_id} joined room {self.room_id}")
        return player_id

    def remove_player(self, player_id: int) -> None:
        """Remove a player from the room."""
        if player_id in self.players:
            del self.players[player_id]
            logger.info(f"Player {player_id} left room {self.room_id}")

    def get_opponent_id(self, player_id: int) -> Optional[int]:
        """Get the opponent's player ID."""
        for pid in self.players:
            if pid != player_id:
                return pid
        return None

    def get_player(self, player_id: int) -> Optional[PlayerConnection]:
        return self.players.get(player_id)

    async def broadcast(self, message: dict, exclude: Optional[int] = None) -> None:
        """Send a message to all players in the room."""
        for pid, player in list(self.players.items()):
            if pid == exclude:
                continue
            await self._safe_send(player.websocket, message)

    async def _safe_send(self, ws, msg: dict) -> None:
        """Safely send a JSON message to a websocket."""
        try:
            await ws.send(json.dumps(msg))
        except websockets.exceptions.ConnectionClosed:
            pass

    async def send_to(self, player_id: int, message: dict) -> None:
        """Send a message to a specific player."""
        player = self.players.get(player_id)
        if player:
            await self._safe_send(player.websocket, message)


# ── Room Manager ───────────────────────────────────────────────────────────────


class RoomManager:
    """Manages all game rooms."""

    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def create_room(self, room_id: Optional[str] = None) -> str:
        """Create a new room. Generates a random ID if not provided."""
        async with self._lock:
            if room_id is None or room_id == "":
                room_id = self._generate_room_id()
            while room_id in self.rooms:
                room_id = self._generate_room_id()

            self.rooms[room_id] = Room(room_id)
            logger.info(f"Created room {room_id} (total rooms: {len(self.rooms)})")
            return room_id

    async def get_room(self, room_id: str) -> Optional[Room]:
        async with self._lock:
            return self.rooms.get(room_id)

    async def remove_room(self, room_id: str) -> None:
        """Remove a room and cancel its game task."""
        async with self._lock:
            room = self.rooms.pop(room_id, None)
            if room and room.game_task:
                room.game_task.cancel()
            logger.info(f"Removed room {room_id} (total rooms: {len(self.rooms)})")

    async def join_room(self, room_id: str) -> Optional[Room]:
        """Join an existing room. Returns None if room doesn't exist or is full."""
        async with self._lock:
            room = self.rooms.get(room_id)
            if room is None:
                return None
            if room.is_full:
                return None
            return room

    def _generate_room_id(self) -> str:
        """Generate a random 4-character room ID."""
        chars = string.ascii_uppercase + string.digits
        return "".join(random.choices(chars, k=4))

    async def cleanup_empty_rooms(self) -> None:
        """Remove empty rooms."""
        async with self._lock:
            empty_rooms = [rid for rid, room in self.rooms.items() if room.is_empty]
            for rid in empty_rooms:
                del self.rooms[rid]
                logger.info(f"Cleaned up empty room {rid}")


# ── Message Handling ───────────────────────────────────────────────────────────


async def handle_message(
    websocket,
    data: dict,
    room: Room,
    player_id: int,
    room_manager: RoomManager,
) -> None:
    """Route incoming messages to the appropriate handler."""
    msg_type = data.get("type", "")

    if msg_type == "heartbeat":
        player = room.get_player(player_id)
        if player:
            player.last_heartbeat = time.time()

    elif msg_type == "ready":
        player = room.get_player(player_id)
        if player:
            player.ready = True
            logger.info(f"Player {player_id} ready in room {room.room_id}")
            await room.broadcast({"type": "opponent_ready"}, exclude=player_id)

            # Check if both players are ready
            if len(room.players) == 2 and all(
                p.ready for p in room.players.values()
            ):
                await start_game(room)

    elif msg_type == "input":
        if not room.game_started or room.game_over:
            return
        action = data.get("action", "")
        player = room.get_player(player_id)
        if player and player.board:
            await player.input_queue.put(action)

    elif msg_type == "rematch":
        if room.game_over:
            room.rematch_votes.add(player_id)
            opponent_id = room.get_opponent_id(player_id)
            if opponent_id is not None:
                await room.send_to(opponent_id, {"type": "rematch_offer"})

            # Both players want rematch
            if len(room.rematch_votes) >= 2:
                await reset_room(room)

    elif msg_type == "join":
        # Handle re-join or initial join
        pass

    else:
        logger.warning(f"Unknown message type: {msg_type}")


# ── Game Logic ─────────────────────────────────────────────────────────────────


async def start_game(room: Room) -> None:
    """Start the game for a room with both players."""
    seed = random.randint(0, 2**31 - 1)
    room.seed = seed
    room.game_started = True
    room.game_over = False
    room.rematch_votes = set()

    # Create boards for each player
    for pid, player in room.players.items():
        board = Board()
        board.seed(seed + pid * 1000)  # Different subsequence per player
        board.new_piece()
        player.board = board
        player.alive = True

    # Notify both players
    await room.broadcast({"type": "game_start", "seed": seed})

    logger.info(
        f"Game started in room {room.room_id} with seed {seed}"
    )

    # Start game loop
    room.game_task = asyncio.create_task(game_loop(room))


async def game_loop(room: Room) -> None:
    """Main game loop: process input, apply gravity, check game over, send state."""
    try:
        while room.game_started and not room.game_over:
            now = time.time()
            any_ticked = False

            # Process input queues and gravity for both players
            for pid, player in list(room.players.items()):
                if not player.alive or player.board is None:
                    continue

                board = player.board

                # Drain input queue
                while not player.input_queue.empty():
                    try:
                        action = player.input_queue.get_nowait()
                        await process_input(board, action, room, pid)
                    except asyncio.QueueEmpty:
                        break

                # Per-player gravity tick
                drop_interval = board.get_drop_interval() / 1000.0
                if now - player.last_tick_time >= drop_interval:
                    board.tick()  # tick() handles lock, clear, spawn internally
                    lines = board.get_last_lines_cleared()
                    if lines > 0:
                        _send_garbage_to_opponent(room, pid, lines)
                    player.last_tick_time = now
                    any_ticked = True

                    # Check if player is still alive
                    if board.is_top_out():
                        player.alive = False

            # Send state update periodically
            await send_game_state(room)

            # Check game over
            await check_game_over(room)
            if room.game_over:
                break

            await asyncio.sleep(0.05)  # 50ms loop for responsive input

    except asyncio.CancelledError:
        logger.info(f"Game loop cancelled for room {room.room_id}")
    except Exception as e:
        logger.error(f"Game loop error in room {room.room_id}: {e}")
        raise


def _send_garbage_to_opponent(room: Room, player_id: int, lines_cleared: int) -> None:
    """Calculate and send garbage lines to the opponent based on lines cleared."""
    attack = Board.get_attack_lines(lines_cleared)
    if attack > 0:
        opponent_id = room.get_opponent_id(player_id)
        if opponent_id is not None:
            opponent = room.get_player(opponent_id)
            if opponent and opponent.board:
                opponent.board.set_garbage_queue(attack)
                logger.info(
                    f"Player {player_id} cleared {lines_cleared} lines, "
                    f"sending {attack} garbage lines"
                )


async def process_input(board: Board, action: str, room: Room, player_id: int) -> None:
    """Process a single player input action."""
    if action == "left":
        board.move(-1, 0)
    elif action == "right":
        board.move(1, 0)
    elif action == "down":
        board.move(0, 1)
    elif action == "rotate":
        board.rotate()
    elif action == "drop":
        board.hard_drop()
        board.lock_piece()
        lines_cleared = board.clear_lines()
        if lines_cleared > 0:
            _send_garbage_to_opponent(room, player_id, lines_cleared)
        # Spawn next piece
        if not board.new_piece():
            pass  # Top-out will be detected in game loop
    elif action == "hold":
        board.hold()


def _render_grid_with_piece(board: Board) -> list:
    """Render the board grid with the current piece overlaid."""
    grid = board.get_grid()
    if board.current_piece and board.current_piece in PIECE_SHAPES:
        shape = PIECE_SHAPES[board.current_piece][board.current_rotation]
        idx = PIECE_INDEX[board.current_piece]
        for cell in shape:
            row = board.current_y + cell[0]
            col = board.current_x + cell[1]
            if 0 <= row < len(grid) and 0 <= col < len(grid[0]):
                if grid[row][col] == 0:
                    grid[row][col] = idx
    return grid


async def send_game_state(room: Room) -> None:
    """Send current game state to both players."""
    for pid, player in list(room.players.items()):
        if player.board is None:
            continue

        opponent_id = room.get_opponent_id(pid)
        opponent = room.get_player(opponent_id) if opponent_id else None

        # Render grids with current pieces overlaid
        own_grid = _render_grid_with_piece(player.board)

        opp_grid = None
        opp_score = 0
        if opponent and opponent.board:
            opp_grid = _render_grid_with_piece(opponent.board)
            opp_score = opponent.board.score

        next_piece = -1
        hold_piece = -1
        if player.board.next_pieces:
            next_piece = PIECES.index(player.board.next_pieces[0])
        if player.board.hold_piece:
            hold_piece = PIECES.index(player.board.hold_piece)

        # Current piece info for client-side ghost rendering
        current_piece_idx = -1
        current_x = 0
        current_y = 0
        current_rotation = 0
        if player.board.current_piece:
            current_piece_idx = PIECES.index(player.board.current_piece)
            current_x = player.board.current_x
            current_y = player.board.current_y
            current_rotation = player.board.current_rotation

        # Next pieces list for preview
        next_pieces = []
        for p in player.board.next_pieces:
            next_pieces.append(PIECES.index(p))

        state_msg = {
            "type": "state",
            "board": own_grid,
            "opponent_board": opp_grid,
            "score": player.board.score,
            "opponent_score": opp_score,
            "level": player.board.level,
            "lines": player.board.lines_cleared_total,
            "next_piece": next_piece,
            "next_pieces": next_pieces,
            "hold_piece": hold_piece,
            "garbage": player.board.garbage_queue,
            "current_piece": current_piece_idx,
            "current_x": current_x,
            "current_y": current_y,
            "current_rotation": current_rotation,
            "ghost_y": player.board.get_ghost_position(),
        }
        await room.send_to(pid, state_msg)


async def check_game_over(room: Room) -> None:
    """Check if either player has topped out."""
    if room.game_over:
        return

    for pid, player in list(room.players.items()):
        if player.board and player.board.is_top_out():
            opponent_id = room.get_opponent_id(pid)
            if opponent_id is not None:
                # pid topped out — they lose, opponent wins
                await room.send_to(pid, {
                    "type": "game_over",
                    "winner": "opponent",
                    "reason": "top_out",
                })
                await room.send_to(opponent_id, {
                    "type": "game_over",
                    "winner": "you",
                    "reason": "top_out",
                })
                room.game_over = True
                logger.info(
                    f"Game over in room {room.room_id}, player {opponent_id} wins"
                )
                return

    # If a player disconnected, the other wins
    if len(room.players) < 2:
        remaining_pid = list(room.players.keys())[0] if room.players else None
        if remaining_pid is not None:
            await room.send_to(
                remaining_pid,
                {
                    "type": "game_over",
                    "winner": "you",
                    "reason": "opponent_disconnected",
                },
            )
            room.game_over = True


async def reset_room(room: Room) -> None:
    """Reset the room for a rematch."""
    room.game_started = False
    room.game_over = False
    room.rematch_votes = set()

    # Reset player states
    for player in room.players.values():
        player.ready = False
        player.alive = True
        player.board = None
        player.input_queue = asyncio.Queue()

    logger.info(f"Room {room.room_id} reset for rematch")
    await start_game(room)


# ── Connection Handling ────────────────────────────────────────────────────────


async def heartbeat_loop(websocket) -> None:
    """Send heartbeat requests to a connected client."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await websocket.send(json.dumps({"type": "heartbeat"}))
            except websockets.exceptions.ConnectionClosed:
                break
    except asyncio.CancelledError:
        pass


async def handle_connection(
    websocket, room_manager: RoomManager
) -> None:
    """Handle a new WebSocket connection."""
    player_id = None
    room = None
    room_id = None

    logger.info(f"New connection from {websocket.remote_address}")

    hb_task = None
    try:
        # Start heartbeat loop
        hb_task = asyncio.create_task(heartbeat_loop(websocket))

        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
                continue

            msg_type = data.get("type")

            # Handle join — must be first message
            if msg_type == "join" and player_id is None:
                req_room_id = data.get("room_id", "")

                if req_room_id and req_room_id != "":
                    # Join existing room
                    room = await room_manager.join_room(req_room_id)
                    if room is None:
                        await websocket.send(
                            json.dumps({
                                "type": "error",
                                "message": "Room not found or is full",
                            })
                        )
                        continue
                    room_id = req_room_id
                else:
                    # Create new room
                    room_id = await room_manager.create_room()
                    room = await room_manager.get_room(room_id)

                if room is None:
                    await websocket.send(
                        json.dumps({"type": "error", "message": "Failed to create/join room"})
                    )
                    continue

                player_id = room.add_player(websocket)

                # Send joined confirmation
                await websocket.send(
                    json.dumps({
                        "type": "joined",
                        "room_id": room_id,
                        "player_id": player_id,
                        "players_count": len(room.players),
                    })
                )

                # Notify existing player if room now has 2
                if len(room.players) == 2:
                    opponent = room.get_opponent_id(player_id)
                    if opponent is not None:
                        await room.send_to(
                            opponent,
                            {
                                "type": "joined",
                                "room_id": room_id,
                                "player_id": opponent,
                                "players_count": 2,
                            },
                        )

                logger.info(
                    f"Player {player_id} {'created' if data.get('room_id', '') == '' else 'joined'} "
                    f"room {room_id}"
                )

            elif msg_type == "heartbeat" and player_id is not None:
                player = room.get_player(player_id) if room else None
                if player:
                    player.last_heartbeat = time.time()
                await websocket.send(json.dumps({"type": "heartbeat"}))

            elif player_id is not None and room is not None:
                await handle_message(
                    websocket, data, room, player_id, room_manager
                )

            else:
                await websocket.send(
                    json.dumps({
                        "type": "error",
                        "message": "Please join a room first (send {\"type\": \"join\"})",
                    })
                )

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Connection closed: {e}")
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        # Cleanup
        if hb_task is not None:
            hb_task.cancel()
        if room and player_id is not None:
            opponent_id = room.get_opponent_id(player_id)
            room.remove_player(player_id)
            # Notify opponent
            if opponent_id is not None:
                await room.send_to(opponent_id, {"type": "opponent_disconnected"})

            if room.is_empty:
                await room_manager.remove_room(room_id) if room_id else None

        await room_manager.cleanup_empty_rooms()
        logger.info(f"Cleaned up connection (room: {room_id}, player: {player_id})")


# ── Server Entry Point ─────────────────────────────────────────────────────────


async def http_health_check(path: str) -> Optional[bytes]:
    """Handle HTTP requests (serving index.html for direct browser access)."""
    if path == "/" or path == "/index.html":
        try:
            with open("index.html", "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None
    return None


async def http_serve_favicon(path: str) -> Optional[bytes]:
    """Serve a minimal favicon (inline SVG) to avoid 404 errors."""
    if path == "/favicon.ico":
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect width="16" height="16" fill="#12122a"/><rect x="2" y="2" width="5" height="5" fill="#00f0f0"/><rect x="9" y="2" width="5" height="5" fill="#f0f000"/><rect x="2" y="9" width="5" height="5" fill="#a000f0"/><rect x="9" y="9" width="5" height="5" fill="#00f000"/></svg>'
        return svg
    return None


async def main():
    """Start the WebSocket server (with optional HTTP serving for convenience)."""
    room_manager = RoomManager()

    async def connection_handler(websocket):
        await handle_connection(websocket, room_manager)

    async def process_request(connection, request):
        """Serve index.html for plain HTTP requests (not WebSocket upgrades)."""
        if "Upgrade" not in request.headers:
            # Try index.html first
            content = await http_health_check(request.path)
            if content is not None:
                return Response(200, "OK", Headers({"Content-Type": "text/html; charset=utf-8"}), content)
            # Try favicon
            favicon = await http_serve_favicon(request.path)
            if favicon is not None:
                return Response(200, "OK", Headers({"Content-Type": "image/svg+xml"}), favicon)
        return None  # Let websockets handle WebSocket upgrades

    logger.info(f"Starting Tetris Battle Server on {HOST}:{PORT}")
    logger.info("Open http://localhost:8765 in your browser to play.")
    logger.info("For two-player mode, open two browser tabs and connect to the same room.")

    async with websockets.serve(
        connection_handler, HOST, PORT,
        max_size=2**20,
        process_request=process_request,
    ):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down")
