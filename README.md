# Bomb Master – 90s‑Style Handheld Reaction Game (ESP32‑C3 + CircuitPython)

## 1. Project Overview
Bomb Master is a 90s‑style handheld electronic reaction game. The OLED shows a command, you perform the matching physical action, the game checks timing/correctness, and you progress through 10 increasingly challenging levels.  
Hardware used: **ESP32‑C3 (Seeed XIAO), SSD1306 128×64 OLED, ADXL345 accelerometer, rotary encoder (with push button on D7 for game input), NeoPixel RGB LED, piezo buzzer, LiPo battery, independent hardware power switch.**

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
SHAKE uses unified thresholds (magnitude > 13 or change > 3 or single change > 4, hold 1.5s); only time factor changes with difficulty.

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
- **Rotary encoder (CLK=D2, DT=D3, SW=D7):** primary input for LEFT/RIGHT rotations and PRESS action (D7 button for game input).  
- **NeoPixel (D0):** visual feedback (splash, success/fail, victory).  
- **Buzzer (D1, PWM):** audio cues for countdown, success, failure, splash.  
- **LiPo battery + independent hardware power switch:** portable power with physical on/off control (hardware switch, no GPIO, completely cuts battery connection).  

## 6. System & Circuit Diagrams
Circuit diagrams are available in the `circuit-diagrams/` folder:
- `circuit_diagrams.pdf` - Circuit schematic and system diagram
- `circuit_diagrams.kicad_sch` - KiCad source file

If you have PNG versions (system_diagram.png, circuit_diagram.png), they can be placed in the same folder.

## 7. Enclosure Design
- Handheld rectangular case; OLED window centered; encoder/button on front.  
- Cutouts for USB‑C and power switch; NeoPixel visible externally.  
- Internal battery compartment with access panel for service/debug.  
- 3D‑printed shell (e.g., PETG/PLA) for rigidity; non‑yellow filament per course constraint.

## 8. Running the Game
1. Flash **CircuitPython for ESP32‑C3** onto the XIAO.  
2. Copy required libs to `/lib/` on CIRCUITPY: `adafruit_ssd1306.mpy`, `adafruit_adxl34x.mpy`, `neopixel.mpy`, `adafruit_bus_device/` (and `adafruit_display_text/` if used).  
3. Copy `code.py` (from `src/` in this repo) to the root of CIRCUITPY as `code.py`.  
4. Eject and reset. Splash plays → press to start → choose difficulty → countdown → play.  

## 9. Repo Structure
```
bomb-master/
├── README.md                  # Project documentation
├── src/
│   └── code.py               # Main game code (CircuitPython)
├── docs/
│   └── CODE_STRUCTURE.md     # Code structure and flow guide
├── circuit-diagrams/
│   ├── system_diagram.png    # System block diagram
│   └── circuit_diagram.png   # Circuit schematic
└── lib/                       # Required CircuitPython libs (copy to device)
    ├── adafruit_ssd1306.mpy
    ├── adafruit_adxl34x.mpy
    ├── neopixel.mpy
    ├── adafruit_bus_device/
    └── adafruit_display_text/ (if used)
```

## 10. Future Improvements
- Add high‑score saving and per‑session stats.  
- More move types or combo chains.  
- Richer 90s‑style sound/visual effects.  
- Dynamic difficulty scaling based on player performance.

