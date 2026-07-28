#!/usr/bin/env python3
"""game.py — Tetris Battle Core Game Logic Module

Provides the Board class with all Tetris game logic, piece definitions,
collision detection, scoring, line clearing, garbage line mechanics,
and the 7-bag randomizer.
"""

import random
from typing import List, Optional, Tuple

# ── Constants ──────────────────────────────────────────────────────────────────

PIECES = ["I", "O", "T", "S", "Z", "J", "L"]

# Each piece is defined as a list of rotation states.
# Each rotation state is a list of [row, col] offsets from the piece origin.
PIECE_SHAPES = {
    "I": [
        [[0, 0], [0, 1], [0, 2], [0, 3]],
        [[0, 2], [1, 2], [2, 2], [3, 2]],
        [[2, 0], [2, 1], [2, 2], [2, 3]],
        [[0, 1], [1, 1], [2, 1], [3, 1]],
    ],
    "O": [
        [[0, 0], [0, 1], [1, 0], [1, 1]],
    ],
    "T": [
        [[0, 1], [1, 0], [1, 1], [1, 2]],
        [[0, 1], [1, 1], [1, 2], [2, 1]],
        [[1, 0], [1, 1], [1, 2], [2, 1]],
        [[0, 1], [1, 0], [1, 1], [2, 1]],
    ],
    "S": [
        [[0, 1], [0, 2], [1, 0], [1, 1]],
        [[0, 1], [1, 1], [1, 2], [2, 2]],
    ],
    "Z": [
        [[0, 0], [0, 1], [1, 1], [1, 2]],
        [[0, 2], [1, 1], [1, 2], [2, 1]],
    ],
    "J": [
        [[0, 0], [1, 0], [1, 1], [1, 2]],
        [[0, 1], [0, 2], [1, 1], [2, 1]],
        [[1, 0], [1, 1], [1, 2], [2, 2]],
        [[0, 1], [1, 1], [2, 0], [2, 1]],
    ],
    "L": [
        [[0, 2], [1, 0], [1, 1], [1, 2]],
        [[0, 1], [1, 1], [2, 1], [2, 2]],
        [[1, 0], [1, 1], [1, 2], [2, 0]],
        [[0, 0], [0, 1], [1, 1], [2, 1]],
    ],
}

# RGB color for each piece (1-indexed in grid)
PIECE_COLORS = {
    "I": (0, 255, 255),    # Cyan
    "O": (255, 255, 0),    # Yellow
    "T": (160, 32, 240),   # Purple
    "S": (0, 255, 0),      # Green
    "Z": (255, 0, 0),      # Red
    "J": (0, 0, 255),      # Blue
    "L": (255, 165, 0),    # Orange
}

# Grid value = piece index in PIECES + 1 (0 = empty, 1-7 = pieces)
PIECE_INDEX = {name: i + 1 for i, name in enumerate(PIECES)}

WALL_KICK_OFFSETS = [
    (0, 0),   # No kick
    (-1, 0),  # Left 1
    (1, 0),   # Right 1
    (0, -1),  # Up 1
    (-1, -1), # Up-left
    (1, -1),  # Up-right
]


# ── Board Class ─────────────────────────────────────────────────────────────────

class Board:
    """Represents a single player's Tetris board with full game logic."""

    def __init__(self, width: int = 10, height: int = 20):
        self.width = width
        self.height = height
        self.grid: List[List[int]] = [[0] * width for _ in range(height)]

        # Current piece state
        self.current_piece: Optional[str] = None
        self.current_rotation: int = 0
        self.current_x: int = 0
        self.current_y: int = 0

        # Game state
        self.score: int = 0
        self.level: int = 1
        self.lines_cleared_total: int = 0

        # Piece queue and hold
        self.bag: List[str] = []
        self.next_pieces: List[str] = []
        self.hold_piece: Optional[str] = None
        self.can_hold: bool = True

        # Garbage
        self.garbage_queue: int = 0

        # Seed for reproducibility
        self._rng = random.Random()

        # Next preview count
        self._preview_count = 1

        # Last action tracking
        self._last_lines_cleared: int = 0
        self._last_lock_was_hard_drop: bool = False

    def seed(self, seed: int) -> None:
        """Set the random seed for deterministic piece generation."""
        self._rng = random.Random(seed)
        self.bag = []
        self.next_pieces = []

    def _generate_bag(self) -> List[str]:
        """Generate a shuffled 7-bag of pieces."""
        bag = PIECES[:]
        self._rng.shuffle(bag)
        return bag

    def _ensure_bag(self) -> None:
        """Ensure the bag has enough pieces."""
        if len(self.bag) < 7:
            self.bag.extend(self._generate_bag())

    def _pop_from_bag(self) -> str:
        """Pop the next piece from the bag, generating a new bag if needed."""
        self._ensure_bag()
        return self.bag.pop(0)

    def _setup_preview(self) -> None:
        """Fill next_pieces preview buffer."""
        while len(self.next_pieces) < self._preview_count + 1:
            self.next_pieces.append(self._pop_from_bag())

    def get_next_piece(self) -> str:
        """Get the next piece from the bag preview."""
        self._setup_preview()
        piece = self.next_pieces.pop(0)
        # Refill
        self.next_pieces.append(self._pop_from_bag())
        return piece

    def new_piece(self, piece_name: Optional[str] = None) -> bool:
        """Spawn a new piece at the top center of the board.
        
        If piece_name is None, pops from bag/preview.
        Returns True if the piece was placed successfully, False if top-out.
        """
        if piece_name is None:
            self._setup_preview()
            piece_name = self.next_pieces.pop(0)
            self.next_pieces.append(self._pop_from_bag())

        self.current_piece = piece_name
        self.current_rotation = 0
        self.current_x = self.width // 2 - 2
        self.current_y = 0
        self.can_hold = True

        # Apply queued garbage before spawning
        if self.garbage_queue > 0:
            self.add_garbage(self.garbage_queue)
            self.garbage_queue = 0

        # Check if new piece can be placed
        if not self.valid_position(piece_name, 0, 0, 0):
            return False  # Top out

        return True

    def valid_position(self, piece: str, rotation: int, dx: int, dy: int) -> bool:
        """Check if a piece at the given rotation and offset is in a valid position."""
        shape = PIECE_SHAPES[piece][rotation]
        for cell in shape:
            row = self.current_y + cell[0] + dy
            col = self.current_x + cell[1] + dx
            if row < 0 or row >= self.height:
                return False
            if col < 0 or col >= self.width:
                return False
            if self.grid[row][col] != 0:
                return False
        return True

    def lock_piece(self) -> None:
        """Lock the current piece into the grid."""
        if self.current_piece is None:
            return
        shape = PIECE_SHAPES[self.current_piece][self.current_rotation]
        idx = PIECE_INDEX[self.current_piece]
        for cell in shape:
            row = self.current_y + cell[0]
            col = self.current_x + cell[1]
            if 0 <= row < self.height and 0 <= col < self.width:
                self.grid[row][col] = idx

    def clear_lines(self) -> int:
        """Clear all complete lines, return the number cleared."""
        new_grid = []
        lines_cleared = 0
        for row in self.grid:
            if all(cell != 0 for cell in row):
                lines_cleared += 1
            else:
                new_grid.append(row)

        # Add empty rows at the top
        for _ in range(lines_cleared):
            new_grid.insert(0, [0] * self.width)

        self.grid = new_grid

        if lines_cleared > 0:
            self.lines_cleared_total += lines_cleared
            # Update level
            new_level = self.lines_cleared_total // 10 + 1
            self.level = min(new_level, 99)

            # Update score
            multipliers = {1: 100, 2: 300, 3: 500, 4: 800}
            self.score += multipliers.get(lines_cleared, 0) * self.level

        self._last_lines_cleared = lines_cleared
        return lines_cleared

    def get_last_lines_cleared(self) -> int:
        """Return the number of lines cleared in the most recent clear_lines call."""
        return self._last_lines_cleared

    def move(self, dx: int, dy: int) -> bool:
        """Move the current piece by (dx, dy). Returns True if moved."""
        if self.current_piece is None:
            return False
        if self.valid_position(self.current_piece, self.current_rotation, dx, dy):
            self.current_x += dx
            self.current_y += dy
            return True
        return False

    def rotate(self) -> bool:
        """Rotate the current piece clockwise with basic wall kicks.
        Returns True if rotated successfully.
        """
        if self.current_piece is None:
            return False
        if self.current_piece == "O":
            return True  # O doesn't rotate

        new_rotation = (self.current_rotation + 1) % len(PIECE_SHAPES[self.current_piece])

        # Try basic wall kick offsets
        for kick_dx, kick_dy in WALL_KICK_OFFSETS:
            if self.valid_position(self.current_piece, new_rotation, kick_dx, kick_dy):
                self.current_rotation = new_rotation
                self.current_x += kick_dx
                self.current_y += kick_dy
                return True
        return False

    def hard_drop(self) -> int:
        """Drop the piece instantly to the lowest valid position.
        Returns the number of rows dropped.
        """
        if self.current_piece is None:
            return 0
        rows = 0
        while self.valid_position(self.current_piece, self.current_rotation, 0, 1):
            self.current_y += 1
            rows += 1
        # Add 2 points per row for hard drop
        self.score += rows * 2
        return rows

    def hold(self) -> bool:
        """Hold the current piece. Can only be used once per turn.
        Returns True if hold was successful.
        """
        if self.current_piece is None or not self.can_hold:
            return False

        prev_hold = self.current_piece
        self.can_hold = False  # Prevent re-hold after new_piece() resets it

        if self.hold_piece is None:
            # First hold — get next piece from bag
            self.current_piece = None
            self.hold_piece = prev_hold
            self.new_piece()
            self.can_hold = False  # Re-assert: can't hold again this turn
        else:
            # Swap with held piece
            swapped_out = self.hold_piece
            self.current_piece = swapped_out
            self.current_rotation = 0
            self.current_x = self.width // 2 - 2
            self.current_y = 0
            if not self.valid_position(self.current_piece, 0, 0, 0):
                # Swap failed — revert to original state
                self.current_piece = prev_hold
                self.hold_piece = swapped_out
                self.current_rotation = 0
                self.current_x = self.width // 2 - 2
                self.current_y = 0
                self.can_hold = True  # Allow another attempt
                return False
            self.hold_piece = prev_hold

        return True

    def tick(self) -> bool:
        """Gravity tick — move the piece down one row.
        Returns True if the piece moved, False if it locked.
        """
        if self.current_piece is None:
            return False
        if self.move(0, 1):
            return True
        else:
            # Piece can't move down — lock it
            self.lock_piece()
            lines = self.clear_lines()
            if not self.new_piece():
                return False  # Game over
            # Return lines cleared info is handled elsewhere
            return True

    def add_garbage(self, count: int) -> None:
        """Add garbage lines from the bottom of the board.
        Each line has one random empty column.
        """
        if count <= 0:
            return

        for _ in range(count):
            # Remove top row
            self.grid.pop(0)
            # Add garbage row at bottom with one random gap
            gap = self._rng.randint(0, self.width - 1)
            new_row = [PIECE_INDEX["T"]] * self.width  # Use T-piece index as garbage marker
            new_row[gap] = 0
            self.grid.append(new_row)

    def is_top_out(self) -> bool:
        """Check if the player has topped out (game over)."""
        return any(self.grid[0][c] != 0 for c in range(self.width))

    def get_grid(self) -> List[List[int]]:
        """Return a copy of the current grid."""
        return [row[:] for row in self.grid]

    def get_ghost_position(self) -> int:
        """Return the y-offset where the current piece would land."""
        if self.current_piece is None:
            return self.current_y
        dy = 0
        while self.valid_position(self.current_piece, self.current_rotation, 0, dy + 1):
            dy += 1
        return self.current_y + dy

    @staticmethod
    def get_attack_lines(lines_cleared: int) -> int:
        """Calculate garbage lines to send based on lines cleared."""
        if lines_cleared <= 1:
            return 0
        elif lines_cleared == 2:
            return 1
        elif lines_cleared == 3:
            return 2
        elif lines_cleared >= 4:
            return 4
        return 0

    def get_drop_interval(self) -> int:
        """Get the drop interval in milliseconds based on current level."""
        return max(50, 1000 - (self.level - 1) * 75)

    def set_garbage_queue(self, count: int) -> None:
        """Queue garbage lines to be applied before next piece spawn."""
        self.garbage_queue += count
