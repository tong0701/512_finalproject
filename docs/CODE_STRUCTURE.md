# Bomb Master - Code Structure & Flow Guide

This document explains the complete code structure and execution flow of the Bomb Master game. Use this as a reference to understand how the game works and to prepare for questions.

---

## 📋 Table of Contents

1. [Overall Architecture](#overall-architecture)
2. [Hardware Setup](#hardware-setup)
3. [Core Components](#core-components)
4. [Game Flow](#game-flow)
5. [Key Functions Explained](#key-functions-explained)
6. [State Machine](#state-machine)
7. [Input Handling](#input-handling)
8. [Display & UI](#display--ui)
9. [Data Flow](#data-flow)

---

## 🏗️ Overall Architecture

The game follows a **single-file architecture** with clear sections:

```
code.py
├── Hardware Initialization (Lines 37-68)
├── Game Configuration (Lines 70-114)
├── Accelerometer Filter Class (Lines 116-187)
├── Encoder Class (Lines 189-252)
├── Helper Functions (Lines 261-323)
├── High Score Management (Lines 325-368)
├── Name Input (Lines 370-435)
├── High Score Board Display (Lines 437-465)
├── Difficulty Selection Menu (Lines 467-509)
├── UI Functions (Lines 511-706)
├── Animation Functions (Lines 642-798)
├── Game Logic Functions (Lines 800-999)
└── Main Game Loop (Lines 1001-1093)
```

**Design Pattern**: Event-driven with state machine (menu → game → results)

---

## 🔌 Hardware Setup

### Pin Mapping
- **OLED (I2C)**: SCL=D5, SDA=D4
- **Accelerometer (I2C)**: Shared bus with OLED
- **Rotary Encoder**: CLK=D2, DT=D3, SW=D7 (button)
- **NeoPixel**: D0
- **Buzzer (PWM)**: D1

### Hardware Initialization Order
1. Initialize I2C bus
2. Initialize OLED display
3. Initialize accelerometer (optional, with error handling)
4. Initialize NeoPixel (optional)
5. Initialize buzzer/PWM (optional)

**Note**: All hardware has try-except blocks to prevent crashes if hardware is missing.

---

## 🧩 Core Components

### 1. AccelerometerFilter Class
**Purpose**: Smooth accelerometer readings and auto-calibration

**How it works**:
- Uses 5-sample moving average filter
- Auto-calibrates on initialization (10 samples, calculates offset)
- Removes gravity offset (assumes Z-axis has ~9.8 m/s² gravity)
- Provides `get_magnitude()` for shake detection

**Key Methods**:
- `calibrate()`: Measures static position, calculates offset
- `read()`: Returns filtered (x, y, z) values
- `get_magnitude()`: Returns total acceleration magnitude

### 2. DebouncedEncoder Class
**Purpose**: Read rotary encoder input reliably

**How it works**:
- Detects CLK falling edge (simplified, fast response)
- Debounce time: 0.001s (very fast)
- Returns 'left' or 'right' direction
- `get_menu_navigation()`: Converts encoder direction to menu navigation (up/down)

**Key Methods**:
- `get_direction()`: Returns 'left' or 'right' or None
- `get_menu_navigation()`: Returns 'up' or 'down' or None
- `reset()`: Resets encoder state

### 3. Game Configuration
**Constants**:
- `TARGET_SCORE = 60`: Score needed to complete rotation actions
- `KNOB_MULTIPLIER = 30`: Points per encoder click
- `REACTION_TIME = 1.0`: Delay before showing new action

**DIFFICULTIES Dictionary**:
- `time_factor`: Multiplies level time (EASY: 1.2x, MEDIUM: 1.0x, HARD: 0.8x)
- `shake_threshold`: Unified magnitude threshold (13)
- `shake_change_threshold`: Accumulated change threshold (3)

**LEVELS List**:
- 10 levels, each with `time` and `moves`
- Time decreases, moves increase with level number

---

## 🎮 Game Flow

### Main Loop Structure

```
Power On
  ↓
Splash Animation (draw_upgraded_splash)
  ↓
"Press to Start" Screen (wait_for_press)
  ↓
Player Name Input (input_player_name)
  - 3 characters (A-Z)
  - Rotary encoder to select
  - Press to confirm each character
  ↓
Difficulty Selection Menu (show_difficulty_menu)
  ↓
┌─────────────────────────────────┐
│ Main Game Loop                  │
│                                 │
│  For each level (0-9):         │
│    ├─ Level Start Screen       │
│    ├─ Countdown (3-2-1-GO)     │
│    ├─ Run Level                │
│    │   ├─ For each move:       │
│    │   │   ├─ Choose action    │
│    │   │   ├─ Wait reaction    │
│    │   │   ├─ Action loop      │
│    │   │   └─ Check success    │
│    │   └─ Level complete       │
│    │                            │
│    ├─ Success?                  │
│    │   ├─ Yes → Next Level     │
│    │   └─ No → Game Over       │
│                                 │
│  All Levels Complete            │
│    └─ Win Screen                │
│                                 │
└─────────────────────────────────┘
  ↓
High Score Check
  - Check if score qualifies for top 3
  - If yes: Add to high score board with player name
  - Show "NEW HIGH SCORE!" animation (if qualified)
  ↓
High Score Board Display (show_high_score_board)
  - Show top 3 scores with player names
  - Press to continue
  ↓
Return to Splash (loop restarts)
```

### Detailed Level Execution Flow

```
run_level() is called
  ↓
Show "LEVEL X" screen → wait_for_press()
  ↓
run_countdown() → 3, 2, 1, GO!
  ↓
Initialize:
  - level_start_time = current time
  - score = 0
  - encoder.reset()
  ↓
┌──────────────────────────────────────┐
│ For each move in level:             │
│                                      │
│  1. Choose action:                  │
│     - Last move = SHAKE             │
│     - Others = random(LEFT/RIGHT/   │
│       PRESS)                         │
│                                      │
│  2. Reaction time delay (1.0s)      │
│     - Check if level time expired   │
│                                      │
│  3. Action execution loop:          │
│     ┌─────────────────────────────┐ │
│     │ while True:                 │ │
│     │   - Check level time        │ │
│     │   - Read encoder            │ │
│     │   - Read accelerometer      │ │
│     │   - Check button            │ │
│     │   - Update display          │ │
│     │   - Check action success    │ │
│     │   - Break if done/timeout   │ │
│     └─────────────────────────────┘ │
│                                      │
│  4. Success?                        │
│     - Yes: score += 10, continue    │
│     - No: return False, score       │
│                                      │
└──────────────────────────────────────┘
  ↓
All moves complete
  ↓
score += 50 (level bonus)
  ↓
draw_success_animation()
  ↓
Return True, score
```

---

## 🔑 Key Functions Explained

### Hardware Functions

#### `safe_show()`
**Purpose**: Safely update OLED display
- Wraps `display.show()` in try-except
- Prevents crashes from I2C errors

#### `tone(freq, duration)`
**Purpose**: Play buzzer sound
- Sets PWM frequency and duty cycle
- Plays for duration, then stops

### UI Functions

#### `draw_centered_text(text, y, color=1)`
**Purpose**: Draw text centered on screen
- Calculates x position: `(128 - text_width) // 2`
- Text width = `len(text) * 6` (6 pixels per char)

#### `draw_game_ui(target, progress_pct, level_time_pct, score, level)`
**Purpose**: Draw complete in-game UI
- Top: Level number (L1-L10) and Score
- Top progress bar: Level time remaining
- Center: Action instruction (LEFT/RIGHT/PRESS/SHAKE)
- Bottom progress bar: Action completion progress
- Updates every 0.05s (controlled in game loop)

#### `show_message_box(title, line1, line2, invert)`
**Purpose**: Display centered message with border
- Used for level start, game over, win screens

### Animation Functions

#### `draw_upgraded_splash()`
**Purpose**: Boot animation
- Phase 1: Bomb grows (8 frames)
- Phase 2: Explosion particles (15 frames)
- Phase 3: Title pops up (12 frames)
- Phase 4: Title flashes twice
- Only plays once per boot (`splash_played` flag)

#### `draw_success_animation()`
**Purpose**: Fireworks animation on level complete
- Creates 36 particles in circle
- Particles spread with gravity
- NeoPixel rainbow effect
- Plays for ~1.5 seconds total

#### `draw_fail_animation()`
**Purpose**: Flash animation on failure
- Inverts screen 5 times
- Red NeoPixel flash
- Descending buzzer tone

### Game Logic Functions

#### `input_player_name()`
**Purpose**: Input 3-character player name before difficulty selection
- Uses rotary encoder to select A-Z
- Press button to confirm each character
- Returns string of 3 characters
- Display shows current selection with cursor underline

#### `show_high_score_board()`
**Purpose**: Display top 3 high scores with player names
- Reads from `highscores.txt`
- Shows: `1. ABC  1234`, `2. XYZ  1000`, etc.
- Waits for button press to continue

#### `is_high_score(score)`
**Purpose**: Check if score qualifies for top 3
- Returns True if board has < 3 entries OR score > 3rd place score

#### `add_high_score(name, score)`
**Purpose**: Add new high score and maintain top 3
- Adds entry, sorts by score (descending), keeps only top 3
- Saves to `highscores.txt`
- Returns updated list

#### `show_difficulty_menu()`
**Purpose**: Difficulty selection screen
- Displays EASY, MEDIUM, HARD with cursor
- Uses encoder to navigate (up/down)
- Button press selects difficulty
- Returns selected difficulty string

#### `run_countdown()`
**Purpose**: 3-2-1-GO countdown
- Shows centered numbers
- Yellow NeoPixel, beep sound
- "GO!" with green NeoPixel, long beep

#### `run_level(level_idx, config, difficulty)`
**Purpose**: Execute a single level
- Parameters:
  - `level_idx`: Level number (0-9)
  - `config`: Level config dict (time, moves)
  - `difficulty`: Difficulty string
- Returns: `(success: bool, score: int)`

**Level Execution Details**:
1. Show level start screen → wait for press
2. Countdown
3. For each move:
   - Choose action (random or SHAKE for last)
   - Wait reaction time
   - Action loop:
     - Check level time limit
     - Detect input (encoder/button/shake)
     - Update progress bar
     - Check if action complete
   - If action failed → return False
4. All moves complete → return True with score

---

## 🎯 State Machine

The game uses an implicit state machine:

```
State: SPLASH
  - Play splash animation
  - Wait for button
  → Transition to MENU

State: MENU
  - Show difficulty selection
  - Navigate with encoder
  - Select with button
  → Transition to GAME

State: GAME
  - For each level:
    - Show level start → wait
    - Countdown
    - Execute moves
    - Check success/failure
  → Transition to RESULT (WIN/GAME_OVER)

State: RESULT
  - Show score/high score
  - Check for new high score
  - Wait for button
  → Transition to SPLASH (loop)
```

---

## 🎮 Input Handling

### Encoder Input (LEFT/RIGHT Actions)
**Detection**:
- `encoder.get_direction()` returns 'left' or 'right'
- Checked every loop iteration (0.01s delay)
- For LEFT action: accumulate score when direction == 'left'
- For RIGHT action: accumulate score when direction == 'right'
- Score increases by `KNOB_MULTIPLIER` (30) per click
- When `accumulated_score >= TARGET_SCORE` (60), action complete

### Button Input (PRESS Action)
**Detection**:
- `button.value == False` means pressed (pull-up resistor)
- Checked every loop iteration
- When PRESS action active and button pressed → action complete

### Accelerometer Input (SHAKE Action)
**Detection** (Multi-threshold approach):
1. **Magnitude trigger**: `current_magnitude > 13`
2. **Change trigger**: `accumulated_change > 3` (within 0.2s window)
3. **Big change trigger**: `magnitude_change > 4` (single large change)

**Hold mechanism**:
- Once triggered, must hold for `shake_hold_duration` (1.5s)
- Progress bar shows hold progress
- If trigger conditions met, action completes after hold time

### Menu Navigation
**Detection**:
- `encoder.get_menu_navigation()` converts encoder direction to menu direction
- Right rotation = Down (next option)
- Left rotation = Up (previous option)
- Menu polls at high frequency (0.001s delay) for responsiveness

---

## 📺 Display & UI

### Screen Layout (128x64 pixels)

**In-Game UI** (`draw_game_ui`):
```
┌────────────────────────────────────┐
│ L1              S:100              │  ← Top bar (Level & Score)
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │  ← Level time progress bar
│                                    │
│           CUT BLUE                 │  ← Action theme
│           << LEFT                  │  ← Action instruction
│                                    │
│                                    │
│        ━━━━━━━━━━━━━━━━━━         │  ← Action progress bar
└────────────────────────────────────┘
```

**Menu UI** (`show_difficulty_menu`):
```
┌────────────────────────────────────┐
│                                    │
│           > EASY                   │  ← y=8
│             MEDIUM                 │  ← y=21
│             HARD                   │  ← y=34
│                                    │
│         Rotate/Press               │  ← y=48
└────────────────────────────────────┘
```

**Message Box** (`show_message_box`):
```
┌────────────────────────────────────┐
│ ╔═══════════════════════════════╗ │
│ ║          TITLE                ║ │  ← Title (y=15)
│ ║                               ║ │
│ ║          Line 1               ║ │  ← Line 1 (y=30)
│ ║          Line 2               ║ │  ← Line 2 (y=42)
│ ╚═══════════════════════════════╝ │
└────────────────────────────────────┘
```

### Display Update Strategy
- **Game UI**: Updated every 0.05s (20 FPS) in game loop
- **Menu**: Updated every loop iteration (high frequency)
- **Animations**: Frame-based (0.04-0.05s per frame)

---

## 📊 Data Flow

### Score Flow
```
Each successful action: +10 points
Level complete bonus: +50 points
Total score = sum of all level scores
```

### High Score Flow
```
Game ends
  ↓
Check: is_high_score(total_score)?
  - Compares with 3rd place or checks if board has < 3 entries
  ↓
Yes → Add player_name and score to high score board
      → Sort and keep top 3
      → Save to highscores.txt (format: "NAME,SCORE")
      → Show "NEW HIGH SCORE!" animation
  ↓
Show high score board (top 3 with names)
  ↓
Press to continue
```

### Name Input Flow
```
After splash screen
  ↓
Display "ENTER NAME"
  ↓
For each of 3 characters:
  - Rotate encoder: Select A-Z
  - Press: Confirm character → Move to next
  ↓
After 3rd character confirmed:
  - Press again → Proceed to difficulty selection
```

### Time Management
```
Level start:
  level_start_time = current_time
  level_time_limit = base_time * difficulty_factor

Each loop:
  elapsed = current_time - level_start_time
  level_time_pct = elapsed / level_time_limit
  
  if elapsed >= level_time_limit:
    → Game Over
```

### Action Progress Tracking

**Rotation Actions (LEFT/RIGHT)**:
```
accumulated_score = 0
Each encoder click in correct direction:
  accumulated_score += KNOB_MULTIPLIER (30)
  
progress_pct = accumulated_score / TARGET_SCORE (60)
  
When progress_pct >= 1.0:
  → Action complete
```

**SHAKE Action**:
```
shake_triggered = False
shake_trigger_time = 0

When shake detected:
  shake_triggered = True
  shake_trigger_time = current_time

progress_pct = (current_time - shake_trigger_time) / 1.5

When progress_pct >= 1.0:
  → Action complete
```

---

## 🔄 Common Patterns

### Error Handling Pattern
```python
try:
    # Hardware operation
    display.show()
except:
    pass  # Fail silently, prevent crash
```

### Hardware Check Pattern
```python
if pixels:
    try:
        pixels.fill((255, 0, 0))
    except:
        pass
```

### Non-blocking Loop Pattern
```python
while True:
    # Do work
    # Check conditions
    time.sleep(0.01)  # Prevent freeze
```

### Progress Bar Drawing Pattern
```python
# Draw border
display.rect(x, y, width, height, 1)

# Calculate fill
fill_w = int(progress_pct * (width - 2))
fill_w = min(max(fill_w, 0), width - 2)  # Clamp

# Draw fill
if fill_w > 0:
    display.fill_rect(x + 1, y + 1, fill_w, height - 2, 1)
```

---

## 📝 Key Constants Reference

| Constant | Value | Purpose |
|----------|-------|---------|
| `TARGET_SCORE` | 60 | Score needed to complete rotation actions |
| `KNOB_MULTIPLIER` | 30 | Points per encoder click |
| `REACTION_TIME` | 1.0s | Delay before showing new action |
| `shake_hold_duration` | 1.5s | Time to hold shake action |
| `debounce_time` | 0.001s | Encoder debounce time |
| `display_update_interval` | 0.05s | UI update frequency |

---

## 🎓 Understanding the Code for Questions

### How to explain the game flow:
1. **Start**: Splash animation → difficulty selection → game begins
2. **Level structure**: 10 levels, increasing difficulty
3. **Move execution**: Random actions (LEFT/RIGHT/PRESS), last is always SHAKE
4. **Scoring**: +10 per move, +50 per level
5. **Time management**: Each level has time limit, difficulty affects time
6. **End conditions**: Time runs out → Game Over, all levels complete → Win

### How to explain input detection:
1. **Encoder**: Detects CLK falling edge, checks DT pin for direction
2. **Button**: Pull-up resistor, False = pressed
3. **Shake**: Multi-threshold (magnitude + change + big change), must hold 1.5s

### How to explain filtering:
1. **Accelerometer**: 5-sample moving average, auto-calibrates on boot
2. **Encoder**: Debounce (0.001s) to prevent noise

### How to explain difficulty:
- Only affects **time factor** (EASY: 1.2x, MEDIUM: 1.0x, HARD: 0.8x)
- Shake thresholds are **unified** across all difficulties
- More time = easier to complete moves

---

## 🚀 Quick Reference for Common Questions

**Q: How does the encoder work?**
- A: Detects CLK falling edge, checks DT pin state to determine direction. Uses debouncing (0.001s) for reliability.

**Q: How is shake detected?**
- A: Three triggers: total magnitude > 13, accumulated change > 3, or single change > 4. Must hold for 1.5 seconds after trigger.

**Q: How does scoring work?**
- A: +10 points per successful action, +50 bonus per completed level. Top 3 high scores saved with player names to `highscores.txt`.

**Q: What happens when time runs out?**
- A: Game immediately ends, shows Game Over screen, checks for high score.

**Q: How are actions chosen?**
- A: Random selection from LEFT/RIGHT/PRESS for first N-1 moves. Last move is always SHAKE.

**Q: How does difficulty affect gameplay?**
- A: Only affects time limit (multiplier: 1.2x/1.0x/0.8x). All other mechanics stay the same.

**Q: How does the high score board work?**
- A: Before difficulty selection, players enter 3-character name (A-Z) using encoder. Top 3 scores are saved with names to onboard memory. High score board displays after game ends.

---

**End of Guide**

Use this document to understand the code structure and prepare for technical questions about the game implementation.

