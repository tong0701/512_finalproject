"""
Bomb Master - Bop-It Style Reaction Game for ESP32-C3 (CircuitPython)

Hardware Pin Map:
- OLED SSD1306 (I2C): SCL=D5, SDA=D4
- ADXL345 Accelerometer (I2C): Shared bus
- Rotary Encoder: CLK=D2, DT=D3, SW=D7 (PRESS button for game input)
- NeoPixel RGB LED: D0
- Buzzer PWM: D1
- LiPo Battery + Independent Power Switch (hardware switch, controls battery connection, no GPIO)

Required Libraries (place in /lib folder):
- adafruit_ssd1306
- adafruit_framebuf (usually bundled)
- adafruit_adxl34x
- neopixel (usually built-in)

Game Features:
- Difficulty selection (EASY, MEDIUM, HARD)
- 10 levels with progressive difficulty
- 4 action types (LEFT, RIGHT, PRESS, SHAKE)
- Score system with high score persistence
- Filtered accelerometer with calibration
- Improved encoder detection
- Polished animations and UI
"""

import time
import board
import busio
import digitalio
import neopixel
import random
import adafruit_ssd1306
import adafruit_adxl34x

# ==================== HARDWARE INITIALIZATION ====================

# I2C Bus
try:
    i2c = busio.I2C(board.D5, board.D4, frequency=1000000)
except:
    i2c = busio.I2C(board.D5, board.D4)

# OLED Display
display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

# Accelerometer
accel = None
try:
    accel = adafruit_adxl34x.ADXL345(i2c)
except:
    pass

# NeoPixel RGB LED (D0)
pixels = None
try:
    pixels = neopixel.NeoPixel(board.D0, 1, brightness=0.3)
except:
    pass

# Buzzer
buzzer = None
try:
    import pwmio
    buzzer = pwmio.PWMOut(board.D1, variable_frequency=True)
except:
    pass

# ==================== GAME CONFIGURATION ====================

# Base game settings
TARGET_SCORE = 60
KNOB_MULTIPLIER = 30
REACTION_TIME = 1.0

# Difficulty settings (ordered: EASY, MEDIUM, HARD)
DIFFICULTIES = {
    "EASY": {
        "time_factor": 1.2,
        "shake_threshold": 13,  # Unified threshold: total magnitude (range ~10-16 based on user data)
        "shake_change_threshold": 3,  # Unified threshold: accumulated change (adjacent change ~1-5)
        "name": "EASY"
    },
    "MEDIUM": {
        "time_factor": 1.0,
        "shake_threshold": 13,  # Unified threshold, same for all difficulties
        "shake_change_threshold": 3,  # Unified threshold
        "name": "MEDIUM"
    },
    "HARD": {
        "time_factor": 0.8,
        "shake_threshold": 13,  # Unified threshold, same for all difficulties
        "shake_change_threshold": 3,  # Unified threshold
        "name": "HARD"
    }
}

# Ensure order: EASY, MEDIUM, HARD
DIFFICULTY_ORDER = ["EASY", "MEDIUM", "HARD"]

# Level definitions (base time and moves)
LEVELS = [
    {"time": 25.0, "moves": 3},
    {"time": 22.0, "moves": 4},
    {"time": 19.0, "moves": 5},
    {"time": 17.0, "moves": 6},
    {"time": 14.0, "moves": 7},
    {"time": 12.0, "moves": 8},
    {"time": 10.0, "moves": 9},
    {"time": 8.5, "moves": 10},
    {"time": 7.0, "moves": 11},
    {"time": 6.0, "moves": 12},
]

# ==================== ACCELEROMETER FILTERING ====================

class AccelerometerFilter:
    """5-sample moving average filter for accelerometer"""
    def __init__(self, accel_sensor):
        self.accel = accel_sensor
        self.samples = [[0, 0, 0] for _ in range(5)]
        self.index = 0
        self.calibrated = False
        self.offset = [0, 0, 0]
        
        # Auto-calibration on init
        if self.accel:
            self.calibrate()
    
    def calibrate(self):
        """Auto-calibrate accelerometer (zero offset)"""
        if not self.accel:
            return
        
        samples = []
        for _ in range(10):
            try:
                x, y, z = self.accel.acceleration
                samples.append([x, y, z])
            except:
                pass
            time.sleep(0.05)
        
        if samples:
            # Calculate average (expected gravity on Z axis ~9.8)
            avg_x = sum(s[0] for s in samples) / len(samples)
            avg_y = sum(s[1] for s in samples) / len(samples)
            avg_z = sum(s[2] for s in samples) / len(samples)
            
            # Set offset (assuming device is stationary)
            self.offset = [avg_x, avg_y, avg_z - 9.8]
            self.calibrated = True
    
    def read(self):
        """Read filtered acceleration values"""
        if not self.accel:
            return (0, 0, 9.8)
        
        try:
            x, y, z = self.accel.acceleration
            # Apply offset calibration
            if self.calibrated:
                x -= self.offset[0]
                y -= self.offset[1]
                z -= self.offset[2]
            
            # Add to circular buffer
            self.samples[self.index] = [x, y, z]
            self.index = (self.index + 1) % 5
            
            # Calculate moving average
            avg_x = sum(s[0] for s in self.samples) / 5
            avg_y = sum(s[1] for s in self.samples) / 5
            avg_z = sum(s[2] for s in self.samples) / 5
            
            return (avg_x, avg_y, avg_z)
        except:
            return (0, 0, 9.8)
    
    def get_magnitude(self):
        """Get total acceleration magnitude"""
        x, y, z = self.read()
        return (x**2 + y**2 + z**2)**0.5

# Initialize filtered accelerometer
accel_filter = AccelerometerFilter(accel)

# ==================== ENCODER WITH DEBOUNCING ====================

class DebouncedEncoder:
    """Simplified encoder - direct response, removed delay restrictions"""
    def __init__(self, pin_clk, pin_dt):
        self.clk = digitalio.DigitalInOut(pin_clk)
        self.clk.direction = digitalio.Direction.INPUT
        self.clk.pull = digitalio.Pull.UP
        
        self.dt = digitalio.DigitalInOut(pin_dt)
        self.dt.direction = digitalio.Direction.INPUT
        self.dt.pull = digitalio.Pull.UP
        
        self.last_clk = self.clk.value
        self.last_dt = self.dt.value
        self.last_edge_time = time.monotonic()
        self.debounce_time = 0.001  # Reduced debounce time for faster response
    
    def get_direction(self):
        """Get encoder direction - simplified version, immediate response"""
        clk = self.clk.value
        dt = self.dt.value
        now = time.monotonic()
        
        direction = None
        
        # Only detect CLK falling edge (simplified, faster response)
        if self.last_clk and not clk:
            if now - self.last_edge_time >= self.debounce_time:
                self.last_edge_time = now
                if dt:
                    direction = 'right'
                else:
                    direction = 'left'
                # Update state immediately
                self.last_clk = clk
                self.last_dt = dt
                return direction
        
        self.last_clk = clk
        self.last_dt = dt
        return None
    
    def get_menu_navigation(self):
        """
        Get menu navigation direction - directly uses get_direction
        Right = Down (next)
        Left = Up/Previous
        """
        direction = self.get_direction()
        
        if direction == 'right':
            return 'down'
        elif direction == 'left':
            return 'up'
        
        return None
    
    def reset(self):
        """Reset encoder state"""
        self.last_clk = self.clk.value
        self.last_dt = self.dt.value
        self.last_edge_time = time.monotonic()

# Initialize encoder
encoder = DebouncedEncoder(board.D2, board.D3)

# Button (encoder switch)
button = digitalio.DigitalInOut(board.D7)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

# ==================== HELPER FUNCTIONS ====================

def safe_show():
    """Safely update display"""
    try:
        display.show()
    except:
        pass

def tone(freq, duration):
    """Play buzzer tone"""
    if buzzer:
        try:
            buzzer.frequency = int(freq)
            buzzer.duty_cycle = 32768
            time.sleep(duration)
            buzzer.duty_cycle = 0
        except:
            pass
    else:
        time.sleep(duration)

def draw_centered_text(text, y, color=1):
    """Draw centered text"""
    x = max(0, (128 - len(text) * 6) // 2)
    display.text(text, x, y, color)

def draw_bold_text(text, x, y, color=1):
    """Draw bold text by drawing twice with 1px offset"""
    display.text(text, x, y, color)
    display.text(text, x + 1, y, color)
    # Optional: draw with vertical offset for enhanced bold effect
    # display.text(text, x, y + 1, color)

def draw_large_text(text, x, y, color=1, scale=2):
    """Draw larger text by scaling (simple pixel doubling)"""
    # Simple scaling: each character drawn as 2x2 pixel block
    # Note: This is simplified version, better effect requires custom font
    for i, char in enumerate(text):
        char_x = x + i * 6 * scale
        # Draw character multiple times (offset) to simulate scaling
        display.text(char, char_x, y, color)
        if scale >= 2:
            display.text(char, char_x + 1, y, color)
            display.text(char, char_x, y + 1, color)
            display.text(char, char_x + 1, y + 1, color)

def draw_centered_bold_text(text, y, color=1):
    """Draw centered bold text"""
    x = max(0, (128 - len(text) * 6) // 2)
    draw_bold_text(text, x, y, color)

def wait_for_press():
    """Wait for button press"""
    while True:
        encoder.get_direction()  # Keep encoder active
        if button.value == False:
            tone(1500, 0.1)
            while button.value == False:
                time.sleep(0.01)
            time.sleep(0.1)
            return
        time.sleep(0.01)

# ==================== HIGH SCORE MANAGEMENT ====================

HIGH_SCORES_FILE = "highscores.txt"

def load_high_scores():
    """Load top 3 high scores from file"""
    try:
        with open(HIGH_SCORES_FILE, 'r') as f:
            lines = f.readlines()
            scores = []
            for line in lines[:3]:  # Only top 3
                parts = line.strip().split(',')
                if len(parts) == 2:
                    name = parts[0].strip()
                    score = int(parts[1].strip())
                    scores.append({'name': name, 'score': score})
            return scores
    except:
        return []

def save_high_scores(scores):
    """Save top 3 high scores to file"""
    try:
        with open(HIGH_SCORES_FILE, 'w') as f:
            for entry in scores[:3]:  # Only save top 3
                f.write(f"{entry['name']},{entry['score']}\n")
    except:
        pass

def add_high_score(name, score):
    """Add a new high score and return updated list (top 3)"""
    scores = load_high_scores()
    scores.append({'name': name, 'score': score})
    scores.sort(key=lambda x: x['score'], reverse=True)  # Sort by score descending
    scores = scores[:3]  # Keep only top 3
    save_high_scores(scores)
    return scores

def is_high_score(score):
    """Check if score qualifies for high score board (top 3)"""
    scores = load_high_scores()
    if len(scores) < 3:
        return True
    return score > scores[-1]['score']  # Compare with 3rd place

# ==================== NAME INPUT ====================

def input_player_name():
    """Input player name (3 characters) using encoder"""
    name = ['A', 'A', 'A']  # Initial letters
    current_pos = 0  # Current character position (0, 1, 2)
    current_char_idx = 0  # Current character index in alphabet (0-25 for A-Z)
    
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    
    while True:
        display.fill(0)
        display.rect(0, 0, 128, 64, 1)
        
        # Title
        draw_centered_text("ENTER NAME", 8, 1)
        
        # Display name with cursor
        name_str = ''.join(name)
        x_start = (128 - len(name_str) * 6) // 2
        y_pos = 28
        
        for i, char in enumerate(name_str):
            x_pos = x_start + i * 6
            if i == current_pos:
                # Draw cursor (underline or highlight)
                display.fill_rect(x_pos - 1, y_pos + 8, 8, 2, 1)
                display.text(char, x_pos, y_pos, 0)  # Inverted
            else:
                display.text(char, x_pos, y_pos, 1)
        
        # Instructions
        draw_centered_text("Rotate: Change", 45, 1)
        draw_centered_text("Press: Confirm", 54, 1)
        
        safe_show()
        
        # Handle encoder navigation
        direction = encoder.get_direction()
        if direction == 'right':
            current_char_idx = (current_char_idx + 1) % 26
            name[current_pos] = alphabet[current_char_idx]
            tone(600, 0.02)
            time.sleep(0.05)
        elif direction == 'left':
            current_char_idx = (current_char_idx - 1) % 26
            name[current_pos] = alphabet[current_char_idx]
            tone(600, 0.02)
            time.sleep(0.05)
        
        # Handle button press
        if button.value == False:
            tone(1500, 0.1)
            while button.value == False:
                time.sleep(0.01)
            time.sleep(0.1)
            
            # Move to next character
            current_pos += 1
            if current_pos >= 3:
                # All characters selected, return name
                return ''.join(name)
            # Reset character index for next position
            current_char_idx = alphabet.index(name[current_pos])
        
        time.sleep(0.01)

# ==================== HIGH SCORE BOARD DISPLAY ====================

def show_high_score_board():
    """Display top 3 high scores"""
    scores = load_high_scores()
    
    while True:
        display.fill(0)
        display.rect(0, 0, 128, 64, 1)
        
        # Title
        draw_centered_text("HIGH SCORES", 5, 1)
        
        # Display top 3 scores
        y_start = 18
        for i, entry in enumerate(scores[:3]):
            rank = f"{i+1}."
            name = entry['name']
            score = entry['score']
            line = f"{rank} {name}  {score}"
            
            # Left align with some offset
            x_pos = 8
            y_pos = y_start + i * 14
            display.text(line, x_pos, y_pos, 1)
        
        # Instructions
        if len(scores) == 0:
            draw_centered_text("No scores yet", 35, 1)
        
        draw_centered_text("Press to continue", 54, 1)
        
        safe_show()
        
        # Wait for button press
        if button.value == False:
            tone(1500, 0.1)
            while button.value == False:
                time.sleep(0.01)
            time.sleep(0.1)
            return
        
        time.sleep(0.01)

# ==================== DIFFICULTY SELECTION MENU ====================

def show_difficulty_menu():
    """Show difficulty selection menu, return selected difficulty"""
    difficulty_names = DIFFICULTY_ORDER  # Ensure order: EASY, MEDIUM, HARD
    selected_idx = 0  # Default selection: EASY
    
    while True:
        display.fill(0)
        display.rect(0, 0, 128, 64, 1)
        
        # Menu items (centered, y positions: 8, 21, 34)
        for i, diff_name in enumerate(difficulty_names):
            y_pos = 8 + i * 13  # y=8, 21, 34
            prefix = "> " if i == selected_idx else "  "
            text = prefix + diff_name
            x_pos = (128 - len(text) * 6) // 2
            display.text(text, x_pos, y_pos, 1)
        
        # Instructions (bottom, y=48)
        draw_centered_text("Rotate/Press", 48, 1)
        
        safe_show()
        
        # High-speed polling for immediate response
        nav = encoder.get_menu_navigation()
        if nav == 'down':
            selected_idx = (selected_idx + 1) % len(difficulty_names)
            tone(800, 0.02)
            time.sleep(0.02)  # Very short delay
        elif nav == 'up':
            selected_idx = (selected_idx - 1) % len(difficulty_names)
            tone(800, 0.02)
            time.sleep(0.02)  # Very short delay
        
        # Check button
        if button.value == False:
            tone(1500, 0.1)
            while button.value == False:
                time.sleep(0.01)
            time.sleep(0.1)
            return difficulty_names[selected_idx]
        
        time.sleep(0.001)  # Very short delay, maximum frequency polling

# ==================== BOMB EXPLOSION SPLASH ANIMATION ====================

splash_played = False

def draw_upgraded_splash():
    """Bomb explosion animation - explosion effect then BOMB MASTER title pops up"""
    global splash_played
    if splash_played:
        return
    splash_played = True
    
    # Phase 1: Bomb appears (center dot)
    center_x, center_y = 64, 32
    for frame in range(8):
        display.fill(0)
        # Bomb (small dot, gradually grows)
        size = frame * 2
        if size > 0:
            display.fill_rect(center_x - size//2, center_y - size//2, size, size, 1)
        safe_show()
        if pixels:
            try:
                # Red flicker
                pixels.fill((min(255, frame * 30), 0, 0))
            except:
                pass
        time.sleep(0.05)
    
    # Phase 2: Explosion effect (outward spreading particles)
    particles = []
    for angle in range(0, 360, 15):  # 24 particles in different directions
        rad = angle * 3.14159 / 180
        particles.append({
            'x': center_x,
            'y': center_y,
            'vx': __import__('math').cos(rad) * 2,
            'vy': __import__('math').sin(rad) * 2,
            'life': 15
        })
    
    for frame in range(15):
        display.fill(0)
        
        # Draw explosion particles
        for p in particles:
            if p['life'] > 0:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['life'] -= 1
                
                x, y = int(p['x']), int(p['y'])
                if 0 <= x < 128 and 0 <= y < 64:
                    display.fill_rect(x, y, 2, 2, 1)
        
        # Center explosion light
        if frame < 10:
            for i in range(3):
                size = (frame + i) * 3
                display.rect(center_x - size//2, center_y - size//2, size, size, 1)
        
        safe_show()
        
        # NeoPixel red explosion effect
        if pixels:
            try:
                intensity = max(0, 255 - frame * 15)
                pixels.fill((intensity, intensity // 3, 0))
            except:
                pass
        
        if frame == 5:
            tone(200, 0.1)  # Low-pitched explosion sound
        
        time.sleep(0.04)
    
    # Phase 3: Title pops up (scales from center)
    title_frames = 12
    for frame in range(title_frames):
        display.fill(0)
        
        # Title scales from center
        scale = frame / title_frames
        if scale > 0.3:  # Start displaying at 30%
            # Simple scaling effect (simulated with different text sizes)
            if scale < 0.6:
                # Small title
                draw_centered_text("BOMB", 28, 1)
                draw_centered_text("MASTER", 38, 1)
            else:
                # Normal size
                draw_centered_text("BOMB MASTER", 25, 1)
        
        # Remaining explosion particles (fade out)
        for p in particles:
            if p['life'] > 0:
                x, y = int(p['x']), int(p['y'])
                if 0 <= x < 128 and 0 <= y < 64:
                    display.fill_rect(x, y, 1, 1, 1)
        
        safe_show()
        
        # NeoPixel fades to yellow/orange
        if pixels:
            try:
                if frame < title_frames // 2:
                    pixels.fill((255 - frame * 20, 100 + frame * 10, 0))
                else:
                    pixels.fill((155, 200, 0))
            except:
                pass
        
        if frame == 3:
            tone(800, 0.1)  # Title appearance sound
        if frame == 8:
            tone(1200, 0.1)
        
        time.sleep(0.05)
    
    # Final state: Title flashes twice
    for flash in range(2):
        display.fill(0)
        draw_centered_text("BOMB MASTER", 25, 1)
        display.rect(0, 0, 128, 64, 1)
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 255, 0))  # Yellow
            except:
                pass
        tone(1500, 0.1)
        time.sleep(0.2)
        
        display.fill(1)
        draw_centered_text("BOMB MASTER", 25, 0)
        display.rect(0, 0, 128, 64, 0)
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 100, 0))  # Orange
            except:
                pass
        time.sleep(0.15)
    
    # Final state
    display.fill(0)
    draw_centered_text("BOMB MASTER", 25, 1)
    display.rect(0, 0, 128, 64, 1)
    safe_show()
    
    if pixels:
        try:
            pixels.fill(0)
        except:
            pass
    
    time.sleep(0.2)

# ==================== UI DRAWING FUNCTIONS ====================

def draw_game_ui(target, progress_pct, level_time_pct, score=None, level=None):
    """Draw game UI with centered layout - adjusted spacing, optimized PRESS button"""
    display.fill(0)
    display.rect(0, 0, 128, 64, 1)
    
    # Top bar: Level and Score
    if level is not None:
        display.text(f"L{level+1}", 5, 3, 1)
    if score is not None:
        score_str = f"S:{score}"
        display.text(score_str, 128 - len(score_str) * 6 - 5, 3, 1)
    
    # Level time progress bar (moved down to leave space at top)
    if level_time_pct is not None:
        bar_width = 100
        bar_x = (128 - bar_width) // 2
        display.rect(bar_x, 13, bar_width, 4, 1)
        fill_w = int(level_time_pct * (bar_width - 2))
        fill_w = min(max(fill_w, 0), bar_width - 2)
        if fill_w > 0:
            display.fill_rect(bar_x + 1, 14, fill_w, 2, 1)
    
    # Action instruction (centered, increased spacing, optimized PRESS button)
    y_center = 30  # Moved down slightly
    if target == "LEFT":
        draw_centered_text("CUT BLUE", y_center - 8)
        draw_centered_text("<< LEFT", y_center + 2)
    elif target == "RIGHT":
        draw_centered_text("CUT RED", y_center - 8)
        draw_centered_text("RIGHT >>", y_center + 2)
    elif target == "PRESS":
        draw_centered_text("ENTER CODE", y_center - 8)  # Moved up, more space
        draw_centered_text("PRESS", y_center + 2)
        # Button indicator (moved down, larger button and spacing)
        btn_x = (128 - 18) // 2  # Slightly larger
        display.rect(btn_x, y_center + 14, 18, 14, 1)  # Larger button frame
        display.rect(btn_x + 1, y_center + 15, 16, 12, 1)  # Double border, more visible
        if button.value == False:
            display.fill_rect(btn_x + 3, y_center + 17, 12, 10, 1)
    elif target == "SHAKE":
        draw_centered_text("DISARM!!", y_center - 8)
        draw_centered_text("SHAKE IT", y_center + 2)
        # Shake indicator (bold lines)
        shake_x = (128 - 48) // 2
        display.line(shake_x, y_center + 12, shake_x + 48, y_center + 12, 1)
        display.line(shake_x, y_center + 13, shake_x + 48, y_center + 13, 1)  # Bold
    
    # Action progress bar (for rotation actions and SHAKE, moved to bottom)
    if target in ["LEFT", "RIGHT"]:
        bar_width = 80
        bar_x = (128 - bar_width) // 2
        bar_y = 54  # Moved to bottom
        display.rect(bar_x, bar_y, bar_width, 8, 1)
        fill_w = int(progress_pct * (bar_width - 2))
        fill_w = min(max(fill_w, 0), bar_width - 2)
        if fill_w > 0:
            display.fill_rect(bar_x + 1, bar_y + 1, fill_w, 6, 1)
    elif target == "SHAKE":
        # SHAKE action also shows time progress bar
        bar_width = 80
        bar_x = (128 - bar_width) // 2
        bar_y = 54  # Moved to bottom
        display.rect(bar_x, bar_y, bar_width, 8, 1)
        fill_w = int(progress_pct * (bar_width - 2))
        fill_w = min(max(fill_w, 0), bar_width - 2)
        if fill_w > 0:
            display.fill_rect(bar_x + 1, bar_y + 1, fill_w, 6, 1)
    
    safe_show()

def show_message_box(title, line1="", line2="", invert=False):
    """Show centered message box"""
    display.fill(1 if invert else 0)
    color = 0 if invert else 1
    
    # Border
    display.rect(2, 2, 124, 60, color)
    display.rect(4, 4, 120, 56, color)
    
    # Title
    draw_centered_text(title, 15, color)
    
    # Lines
    if line1:
        draw_centered_text(line1, 30, color)
    if line2:
        draw_centered_text(line2, 42, color)
    
    safe_show()

# ==================== ANIMATIONS ====================

def draw_success_animation():
    """Success animation - beautiful fireworks effect, particles float longer"""
    frames = 20  # Increased frames for longer particle float
    center_x, center_y = 64, 32
    
    # Create more firework particles
    particles = []
    for angle in range(0, 360, 10):  # 36 particles in different directions
        rad = angle * 3.14159 / 180
        speed = random.uniform(1.5, 3.0)  # Random speed
        particles.append({
            'x': center_x,
            'y': center_y,
            'vx': __import__('math').cos(rad) * speed,
            'vy': __import__('math').sin(rad) * speed,
            'life': 25,  # Longer life cycle
            'size': random.randint(1, 2)
        })
    
    for frame in range(frames):
        display.fill(0)
        
        # Draw firework particles
        for p in particles:
            if p['life'] > 0:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['life'] -= 1
                p['vy'] += 0.1  # Gravity effect, particles fall
                
                x, y = int(p['x']), int(p['y'])
                if 0 <= x < 128 and 0 <= y < 64:
                    size = p['size']
                    display.fill_rect(x - size, y - size, size * 2 + 1, size * 2 + 1, 1)
        
        # Center burst effect (first few frames)
        if frame < 8:
            for i in range(3):
                size = (frame + i) * 3
                display.rect(center_x - size//2, center_y - size//2, size, size, 1)
        
        safe_show()
        
        # NeoPixel rainbow effect
        if pixels:
            try:
                hue = (frame * 20) % 360
                if hue < 60:
                    pixels.fill((255, hue * 4, 0))
                elif hue < 120:
                    pixels.fill((255 - (hue - 60) * 4, 255, 0))
                elif hue < 180:
                    pixels.fill((0, 255, (hue - 120) * 4))
                else:
                    pixels.fill((0, 255 - (hue - 180) * 4, 255))
            except:
                pass
        
        time.sleep(0.05)  # Slightly slower for smoother effect
    
    # Continue particle fall (additional frames)
    for frame in range(10):
        display.fill(0)
        
        for p in particles:
            if p['life'] > 0:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['life'] -= 1
                p['vy'] += 0.1
                
                x, y = int(p['x']), int(p['y'])
                if 0 <= x < 128 and 0 <= y < 64:
                    size = max(1, p['size'] - frame // 5)  # Gradually shrink
                    display.fill_rect(x - size, y - size, size * 2 + 1, size * 2 + 1, 1)
        
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 255, 100))  # Light yellow
            except:
                pass
        time.sleep(0.04)
    
    # Final fade out
    display.fill(0)
    safe_show()
    if pixels:
        try:
            pixels.fill(0)
        except:
            pass

def draw_fail_animation():
    """Failure animation - quick flash with distinctive sound"""
    frames = 5
    for frame in range(frames):
        invert = (frame % 2 == 0)
        display.fill(1 if invert else 0)
        safe_show()
        
        if pixels:
            try:
                pixels.fill((255, 0, 0) if invert else (0, 0, 0))
            except:
                pass
        
        if frame % 2 == 0:
            # Failure sound: descending pitch
            tone(600 - frame * 50, 0.08)
        else:
            time.sleep(0.05)
    
    # Final low tone
    tone(300, 0.2)
    
    display.fill(0)
    safe_show()
    if pixels:
        try:
            pixels.fill(0)
        except:
            pass

def draw_new_high_score_animation():
    """Animation for new high score"""
    for _ in range(3):
        display.fill(1)
        draw_centered_text("NEW HIGH", 20, 0)
        draw_centered_text("SCORE!", 35, 0)
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 255, 0))
            except:
                pass
        tone(1000, 0.1)
        time.sleep(0.2)
        
        display.fill(0)
        draw_centered_text("NEW HIGH", 20, 1)
        draw_centered_text("SCORE!", 35, 1)
        safe_show()
        if pixels:
            try:
                pixels.fill(0)
            except:
                pass
        time.sleep(0.2)
    
    if pixels:
        try:
            pixels.fill(0)
        except:
            pass

# ==================== GAME LOGIC ====================

def run_countdown():
    """Countdown before level starts - centered display"""
    for i in range(3, 0, -1):
        # Display number centered
        display.fill(0)
        display.rect(0, 0, 128, 64, 1)
        draw_centered_text(str(i), 28, 1)  # Screen center
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 255, 0))
            except:
                pass
        tone(1000, 0.1)
        time.sleep(0.5)
        if pixels:
            try:
                pixels.fill(0)
            except:
                pass
        time.sleep(0.5)
    
    # GO displayed centered
    display.fill(0)
    display.rect(0, 0, 128, 64, 1)
    draw_centered_text("GO!", 28, 1)  # Screen center
    safe_show()
    if pixels:
        try:
            pixels.fill((0, 255, 0))
        except:
            pass
    tone(2000, 0.5)
    time.sleep(0.5)
    if pixels:
        try:
            pixels.fill(0)
        except:
            pass

def run_level(level_idx, config, difficulty):
    """Run a level with difficulty settings"""
    diff_config = DIFFICULTIES[difficulty]
    level_time_limit = config['time'] * diff_config['time_factor']
    moves_cnt = config['moves']
    shake_threshold = diff_config['shake_threshold']
    shake_change_threshold = diff_config['shake_change_threshold']
    
    # Show level start
    show_message_box(f"LEVEL {level_idx+1}", difficulty, "PRESS TO START")
    wait_for_press()
    
    run_countdown()
    
    encoder.reset()
    level_start_time = time.monotonic()
    score = 0
    
    for m in range(moves_cnt):
        # Choose action
        is_shake = (m == moves_cnt - 1)
        if is_shake:
            target = "SHAKE"
        else:
            target = random.choice(["LEFT", "RIGHT", "PRESS"])
        
        # Reaction time
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < REACTION_TIME:
            encoder.get_direction()
            elapsed = time.monotonic() - level_start_time
            if elapsed >= level_time_limit:
                return False, score
            time.sleep(0.01)
        
        encoder.reset()
        done = False
        last_draw_time = 0
        accumulated_score = 0
        
        # SHAKE action special handling: use total magnitude detection + accumulated change
        shake_triggered = False
        shake_trigger_time = 0
        shake_hold_duration = 1.5  # Must hold for 1.5 seconds
        last_magnitude = accel_filter.get_magnitude()  # Record previous magnitude
        accumulated_change = 0  # Accumulated change
        last_change_reset_time = time.monotonic()  # Last time accumulated change was reset
        
        while True:
            direction = encoder.get_direction()
            now = time.monotonic()
            elapsed = time.monotonic() - level_start_time
            
            # Check level time
            if elapsed >= level_time_limit:
                return False, score
            
            level_time_pct = elapsed / level_time_limit
            
            # Rotation detection - simplified version, direct response
            if direction:
                if target == "RIGHT" and direction == "right":
                    accumulated_score += KNOB_MULTIPLIER
                    if accumulated_score >= TARGET_SCORE:
                        done = True
                        score += 10
                        break
                elif target == "LEFT" and direction == "left":
                    accumulated_score += KNOB_MULTIPLIER
                    if accumulated_score >= TARGET_SCORE:
                        done = True
                        score += 10
                        break
            
            # SHAKE detection - optimized: total magnitude + single change
            if target == "SHAKE":
                current_magnitude = accel_filter.get_magnitude()
                magnitude_change = abs(current_magnitude - last_magnitude)
                last_magnitude = current_magnitude
                
                # Accumulated change (within 0.2s window, more sensitive)
                if now - last_change_reset_time > 0.2:  # 0.2s window
                    accumulated_change = 0
                    last_change_reset_time = now
                else:
                    accumulated_change += magnitude_change
                
                # Detection conditions: total magnitude exceeds threshold OR accumulated change exceeds threshold OR single large change
                # Based on user data: magnitude range ~10-16, single change can reach 4-5
                magnitude_trigger = current_magnitude > shake_threshold
                change_trigger = accumulated_change > shake_change_threshold
                big_change_trigger = magnitude_change > 4  # Single large change also triggers (more sensitive)
                
                if magnitude_trigger or change_trigger or big_change_trigger:
                    if not shake_triggered:
                        # First trigger
                        shake_triggered = True
                        shake_trigger_time = now
                    else:
                        # Already triggered, check duration
                        if now - shake_trigger_time >= shake_hold_duration:
                            # Time reached, complete action
                            done = True
                            score += 10
                            break
                # Note: once triggered, maintain triggered state until time is up
                
                # Calculate SHAKE progress (based on time after trigger)
                if shake_triggered:
                    shake_progress = min(1.0, (now - shake_trigger_time) / shake_hold_duration)
                else:
                    shake_progress = 0
            else:
                shake_progress = 0
            
            # Update display
            if now - last_draw_time > 0.05:
                if target in ["LEFT", "RIGHT"]:
                    progress_pct = min(1.0, accumulated_score / TARGET_SCORE)
                elif target == "SHAKE":
                    progress_pct = shake_progress  # SHAKE uses time progress
                else:
                    progress_pct = 0
                draw_game_ui(target, progress_pct, level_time_pct, score, level_idx)
                last_draw_time = now
            
            # Button detection
            if button.value == False:
                if target == "PRESS":
                    done = True
                    score += 10
                    break
            
            time.sleep(0.01)
        
        if not done:
            return False, score
        
        encoder.reset()
    
    # Level complete bonus
    score += 50
    
    # Success animation with distinctive sound
    draw_success_animation()
    if pixels:
        try:
            pixels.fill((0, 255, 0))
        except:
            pass
    # Success sound: ascending pitch
    tone(1000, 0.1)
    time.sleep(0.05)
    tone(1500, 0.1)
    time.sleep(0.05)
    tone(2000, 0.15)
    time.sleep(0.2)
    
    return True, score

# ==================== MAIN GAME LOOP ====================

# Load high scores at startup
high_scores = load_high_scores()

while True:
    try:
        # Splash screen (only on boot)
        draw_upgraded_splash()
        
        # Show "Press to start" after splash
        show_message_box("BOMB MASTER", "PRESS BUTTON", "TO CONTINUE")
        if pixels:
            try:
                pixels.fill((0, 255, 0))
            except:
                pass
        wait_for_press()
        if pixels:
            try:
                pixels.fill(0)
            except:
                pass
        
        # Input player name (before difficulty selection)
        player_name = input_player_name()
        
        # Difficulty selection
        selected_difficulty = show_difficulty_menu()
        
        # Game variables
        current_level = 0
        total_score = 0
        game_active = True
        
        while game_active:
            # Check if all levels complete
            if current_level >= len(LEVELS):
                show_message_box("MISSION", "COMPLETE!", f"Score: {total_score}")
                if pixels:
                    try:
                        for _ in range(2):
                            for c in [(255,0,0), (255,127,0), (255,255,0), (0,255,0), (0,0,255), (75,0,130)]:
                                pixels.fill(c)
                                time.sleep(0.05)
                    except:
                        pass
                tone(1000, 0.2)
                tone(2000, 0.4)
                
                # Check for high score
                if is_high_score(total_score):
                    # Add to high score board
                    high_scores = add_high_score(player_name, total_score)
                    draw_new_high_score_animation()
                    show_message_box("NEW HIGH SCORE!", f"{player_name}: {total_score}", "")
                else:
                    # Show current high scores
                    pass
                
                # Show high score board
                show_high_score_board()
                
                game_active = False
                break
            
            # Run level
            success, level_score = run_level(current_level, LEVELS[current_level], selected_difficulty)
            total_score += level_score
            
            if success:
                # Show level complete
                show_message_box("LEVEL CLEAR", f"Score: {total_score}", "PRESS -> NEXT")
                wait_for_press()
                current_level += 1
            else:
                # Game over
                draw_fail_animation()
                
                # Check for high score
                if is_high_score(total_score):
                    # Add to high score board
                    high_scores = add_high_score(player_name, total_score)
                    draw_new_high_score_animation()
                    show_message_box("GAME OVER", f"New High Score!", f"{player_name}: {total_score}")
                else:
                    show_message_box("GAME OVER", f"Score: {total_score}", "PRESS -> BOARD")
                    wait_for_press()
                
                # Show high score board
                show_high_score_board()
                game_active = False
        
        # Reset splash flag for next game
        splash_played = False
        
    except Exception as e:
        print("Crash:", e)
        import traceback
        traceback.print_exc()
        time.sleep(1)
