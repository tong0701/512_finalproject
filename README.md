# Bomb Master – 90s‑Style Handheld Reaction Game (ESP32‑C3 + CircuitPython)

## 1. Project Overview
Bomb Master is a 90s‑style handheld electronic reaction game. The OLED shows a command, you perform the matching physical action, the game checks timing/correctness, and you progress through 10 increasingly challenging levels.  
Hardware used: **ESP32‑C3 (Seeed XIAO), SSD1306 128×64 OLED, ADXL345 accelerometer, rotary encoder (with push button), NeoPixel RGB LED, piezo buzzer, LiPo battery, power switch.**

## 2. How to Play
### 2.1 Game Actions
- **LEFT** – rotate the encoder left  
- **RIGHT** – rotate the encoder right  
- **PRESS** – press the encoder/button (D7)  
- **SHAKE** – shake the device (detected by ADXL345)

### 2.2 Game Loop Structure
- Splash animation → “PRESS TO START”
- Difficulty selection (Easy / Medium / Hard)
- Level start screen → press to ready → countdown (3,2,1,GO)
- Per‑move instruction (LEFT/RIGHT/PRESS; final move is SHAKE) with time limit and correctness check
- Level up after all moves; failure shows Game Over; after level 10 shows Win screen

## 3. Difficulty Settings
- **Easy:** level time × 1.2  
- **Medium:** level time × 1.0  
- **Hard:** level time × 0.8  
SHAKE uses unified thresholds (magnitude > 13 or change > 3 or single change > 4, hold 0.5s); only time factor changes with difficulty.

## 4. Level Design (10 Levels)

| Level | Time Limit (base, s) | Moves | Notes |
|-------|----------------------|-------|-------|
| 1 | 25.0 | 3 | Last move = SHAKE |
| 2 | 22.0 | 4 | Last move = SHAKE |
| 3 | 19.0 | 5 | Last move = SHAKE |
| 4 | 17.0 | 6 | Last move = SHAKE |
| 5 | 14.0 | 7 | Last move = SHAKE |
| 6 | 12.0 | 8 | Last move = SHAKE |
| 7 | 10.0 | 9 | Last move = SHAKE |
| 8 | 8.5 | 10 | Last move = SHAKE |
| 9 | 7.0 | 11 | Last move = SHAKE |
| 10 | 6.0 | 12 | Last move = SHAKE |

Actual per‑difficulty time = base time × difficulty time factor above.

## 5. Hardware Components & Roles
- **ESP32‑C3 (XIAO):** runs CircuitPython game loop and state machine.  
- **SSD1306 OLED:** shows commands, timers, countdowns, and status.  
- **ADXL345 accelerometer:** detects SHAKE via magnitude/variation thresholds and hold time.  
- **Rotary encoder (CLK=D2, DT=D3, SW=D7):** primary input for LEFT/RIGHT and PRESS.  
- **NeoPixel (D0):** visual feedback (splash, success/fail, victory).  
- **Buzzer (D1, PWM):** audio cues for countdown, success, failure, splash.  
- **LiPo battery + switch:** portable power and hard cutoff.  

## 6. System Diagram
![System Diagram](assignment4-circuit/system_diagram.png)

## 7. Circuit Diagram
![Circuit Diagram](assignment4-circuit/circuit_diagram.png)

## 8. Enclosure Design
- Handheld rectangular case; OLED window centered; encoder/button on front.  
- Cutouts for USB‑C and power switch; NeoPixel visible externally.  
- Internal battery compartment with access panel for service/debug.  
- 3D‑printed shell (e.g., PETG/PLA) for rigidity; non‑yellow filament per course constraint.

## 9. Running the Game
1. Flash **CircuitPython for ESP32‑C3** onto the XIAO.  
2. Copy required libs to `/lib/` on CIRCUITPY: `adafruit_ssd1306.mpy`, `adafruit_adxl34x.mpy`, `neopixel.mpy`, `adafruit_bus_device/` (and `adafruit_display_text/` if used).  
3. Copy `code.py` (from `src/` in this repo) to the root of CIRCUITPY as `code.py`.  
4. Eject and reset. Splash plays → press to start → choose difficulty → countdown → play.  

## 10. Repo Structure
```
bomb-master-game/
├── code.py                    # main game code (CircuitPython)
├── lib/                       # required CircuitPython libs to copy to device
│   ├── adafruit_ssd1306.mpy
│   ├── adafruit_adxl34x.mpy
│   ├── neopixel.mpy
│   ├── adafruit_bus_device/
│   └── adafruit_display_text/ (if used)
├── assignment4-circuit/
│   ├── system_diagram.png
│   └── circuit_diagram.png
└── README.md
```

## 11. Future Improvements
- Add high‑score saving and per‑session stats.  
- More move types or combo chains.  
- Richer 90s‑style sound/visual effects.  
- Dynamic difficulty scaling based on player performance.  

# TECHIN 509: Melody Generator

A Python project for loading, saving, and managing musical melodies represented as sequences of notes.

## Project Overview

This project provides utilities for working with musical melodies in a simple text-based format. Melodies are represented as sequences of note names (e.g., C, D, E, F, G, A, B) and can be loaded from or saved to text files. The project uses a **Bigram model** to learn patterns from existing melodies and generate new ones.

## Features

- **Load melodies** from text files (space or comma-separated)
- **Save melodies** to text files
- **Generate new melodies** using a Bigram probability model trained on existing melodies
- **Error handling** for missing files and invalid inputs
- **Comprehensive test suite** for all functionality

## Project Structure

```
509/
├── README.md              # This file
├── models.py              # Core functions for loading and saving melodies
├── example_usage.py       # Example usage demonstrations
├── data/
│   └── melodies.txt       # Sample melody dataset
└── tests/
    └── test_models.py     # Unit tests for the melody functions
```

## Requirements

- **Python 3.9+** (required for type hints syntax like `list[list[str]]`)

No external dependencies are required - this project uses only Python standard library modules.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/tong0701/melody-generator-509.git
   cd melody-generator-509
   ```

2. Ensure you have Python 3.9 or higher installed:
   ```bash
   python3 --version
   ```

## Usage

### Basic Usage

#### Loading Melodies

```python
from models import load_melodies

# Load melodies from a file
melodies = load_melodies('data/melodies.txt')
print(f"Loaded {len(melodies)} melodies")
for melody in melodies:
    print(' '.join(melody))
```

#### Saving Melodies

```python
from models import save_melodies

# Create and save melodies
new_melodies = [
    ['C', 'E', 'G', 'C'],
    ['D', 'F', 'A'],
    ['G', 'B', 'D', 'G']
]
save_melodies(new_melodies, 'data/generated_melodies.txt')
```

#### Generating Melodies with Bigram Model

```python
from models import (
    load_melodies,
    preprocess_melodies,
    build_bigram_model,
    generate_melody,
    save_melodies
)

# Load and preprocess melodies
melodies = load_melodies('data/melodies.txt')
processed = preprocess_melodies(melodies)

# Train the model
model = build_bigram_model(processed)

# Generate new melodies
new_melody = generate_melody(model, max_length=20)
print(' '.join(new_melody))
```

### Running Examples

Run the example usage script to generate new melodies:

```bash
python3 example_usage.py
```

This will:
1. Load melodies from `data/melodies.txt`
2. Preprocess melodies (add start/end tokens)
3. Train a Bigram model on the loaded melodies
4. Generate 5 new melodies using the trained model
5. Save the generated melodies to `data/generated_melodies.txt`

### Running Tests

Run the test suite to verify all functionality:

```bash
python3 -m pytest tests/
```

Or using unittest:

```bash
python3 -m unittest tests.test_models
```

## Data Format

Melodies are stored in text files where each line represents one melody. Notes can be separated by spaces or commas:

**Space-separated format:**
```
C D E F G A B C
A B C D E
G A B C D E F G
```

**Comma-separated format:**
```
C, D, E, F, G, A, B, C
A, B, C, D, E
```

## API Reference

### `load_melodies(path: str) -> list[list[str]]`

Read melodies from a file and return as a list of note lists.

**Parameters:**
- `path` (str): Path to the file containing melodies

**Returns:**
- `list[list[str]]`: List of melodies, where each melody is a list of notes

**Example:**
```python
melodies = load_melodies('data/melodies.txt')
```

### `save_melodies(melodies: list[list[str]], path: str) -> None`

Save a list of melodies to a file, one melody per line.

**Parameters:**
- `melodies` (list[list[str]]): List of melodies to save
- `path` (str): Path to the output file

**Example:**
```python
save_melodies([['C', 'E', 'G']], 'output.txt')
```

### `preprocess_melodies(melodies: list[list[str]]) -> list[list[str]]`

Add start (^) and end ($) tokens to melodies for training.

**Parameters:**
- `melodies` (list[list[str]]): List of melodies to preprocess

**Returns:**
- `list[list[str]]`: Melodies with start and end tokens added

**Example:**
```python
processed = preprocess_melodies([['C', 'D', 'E']])
# Returns: [['^', 'C', 'D', 'E', '$']]
```

### `build_bigram_model(melodies: list[list[str]]) -> dict`

Build a Bigram model from preprocessed melodies. The model stores transition counts between consecutive notes.

**Parameters:**
- `melodies` (list[list[str]]): Preprocessed melodies with ^ and $ tokens

**Returns:**
- `dict`: Bigram model where `model[note1][note2]` = count of note1→note2 transitions

**Example:**
```python
model = build_bigram_model(processed_melodies)
```

### `generate_melody(model: dict, max_length: int = 20) -> list[str]`

Generate a new melody using the trained Bigram model.

**Parameters:**
- `model` (dict): Trained Bigram model
- `max_length` (int): Maximum length of generated melody (default: 20)

**Returns:**
- `list[str]`: Generated melody as a list of notes

**Example:**
```python
new_melody = generate_melody(model, max_length=15)
```

## Example Output

When running `example_usage.py`, you should see output like:

```
--- Step 1: Loading Data ---
Loaded 8 melodies from data/melodies.txt

--- Step 2: Preprocessing ---
Added start (^) and end ($) tokens to melodies.

--- Step 3: Training Model ---
Model trained. Learned 9 unique notes/states.

--- Step 4: Generating Music ---
Generated 1: C D E F G A B C
Generated 2: A B C D E
Generated 3: G A B C D E F G
Generated 4: C E G
Generated 5: F A C

--- Step 5: Saving Results ---
Saved 5 generated melodies to data/generated_melodies.txt
```

## Testing

The project includes comprehensive unit tests covering:
- Saving and loading melodies
- Error handling for non-existent files
- Empty file handling
- Empty melody list handling

Run tests with:
```bash
python3 -m unittest tests.test_models
```

All tests should pass successfully.

## Error Handling

The functions include error handling for:
- **File not found**: Returns empty list and prints informative error message
- **Empty files**: Returns empty list
- **Invalid file paths**: Gracefully handles exceptions

## Contributing

This is a course project for TECHIN 509. For questions or issues, please open an issue on the GitHub repository.

## License

This project is part of the TECHIN 509 course work.

## Author

Tong - TECHIN 509 Student

