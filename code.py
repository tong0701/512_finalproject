"""
Bomb Master - Bop-It Style Reaction Game for ESP32-C3 (CircuitPython)

Hardware Pin Map:
- OLED SSD1306 (I2C): SCL=D5, SDA=D4
- ADXL345 Accelerometer (I2C): Shared bus
- Rotary Encoder: CLK=D2, DT=D3, SW=D7 (PRESS button)
- NeoPixel RGB LED: D0
- Buzzer PWM: D1
- LiPo Battery + Power Switch

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

# NeoPixel RGB LED (D0) - 灯光部分
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
        "shake_threshold": 13,  # 统一阈值：总magnitude（基于用户数据，范围约10-16）
        "shake_change_threshold": 3,  # 统一阈值：累计变化量（相邻变化约1-5）
        "name": "EASY"
    },
    "MEDIUM": {
        "time_factor": 1.0,
        "shake_threshold": 13,  # 统一阈值，不随难度变化
        "shake_change_threshold": 3,  # 统一阈值
        "name": "MEDIUM"
    },
    "HARD": {
        "time_factor": 0.8,
        "shake_threshold": 13,  # 统一阈值，不随难度变化
        "shake_change_threshold": 3,  # 统一阈值
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
    """Improved encoder with step counting for menu navigation"""
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
        self.debounce_time = 0.002
        self.last_direction = None
        self.last_return_time = time.monotonic()
        self.min_return_interval = 0.01
        
        # 用于菜单导航：累计步数
        self.step_count = 0  # 累计同方向的步数
        self.step_direction = None  # 当前累计的方向
    
    def get_direction(self):
        """Get encoder direction - 立即返回（用于游戏）"""
        clk = self.clk.value
        dt = self.dt.value
        now = time.monotonic()
        
        direction = None
        
        # 检测CLK下降沿
        if self.last_clk and not clk:
            if now - self.last_edge_time >= self.debounce_time:
                self.last_edge_time = now
                if dt:
                    direction = 'right'
                else:
                    direction = 'left'
        
        # 检测上升沿
        elif not self.last_clk and clk:
            if now - self.last_edge_time >= self.debounce_time:
                self.last_edge_time = now
                if not dt:
                    direction = 'right'
                else:
                    direction = 'left'
        
        if direction:
            if now - self.last_return_time < self.min_return_interval:
                if direction == self.last_direction:
                    self.last_clk = clk
                    self.last_dt = dt
                    return None
            
            self.last_direction = direction
            self.last_return_time = now
            self.last_clk = clk
            self.last_dt = dt
            return direction
        
        self.last_clk = clk
        self.last_dt = dt
        return None
    
    def get_menu_navigation(self, steps_required=1):
        """
        获取菜单导航方向 - 更灵敏，只需1步
        向右1步 = 向下（next）
        向左1步 = 返回/向上（prev）
        """
        direction = self.get_direction()
        
        if direction:
            # 立即返回，不需要累计
            if direction == 'right':
                return 'down'  # 向右 = 向下
            else:  # left
                return 'up'  # 向左 = 向上/返回
        
        return None
    
    def reset(self):
        """Reset encoder state"""
        self.last_direction = None
        self.step_count = 0
        self.step_direction = None
        self.last_clk = self.clk.value
        self.last_dt = self.dt.value
        self.last_edge_time = time.monotonic()
        self.last_return_time = time.monotonic()

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
    # 可选：再绘制一次垂直偏移，增强加粗效果
    # display.text(text, x, y + 1, color)

def draw_large_text(text, x, y, color=1, scale=2):
    """Draw larger text by scaling (simple pixel doubling)"""
    # 简单的放大：每个字符绘制为2x2像素块
    # 注意：这是简化版，更好的效果需要自定义字体
    for i, char in enumerate(text):
        char_x = x + i * 6 * scale
        # 绘制字符两次（偏移）模拟放大
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

HIGH_SCORE_FILE = "highscore.txt"

def load_high_score():
    """Load high score from file"""
    try:
        with open(HIGH_SCORE_FILE, 'r') as f:
            return int(f.read().strip())
    except:
        return 0

def save_high_score(score):
    """Save high score to file"""
    try:
        with open(HIGH_SCORE_FILE, 'w') as f:
            f.write(str(score))
    except:
        pass

# ==================== DIFFICULTY SELECTION MENU ====================

def show_difficulty_menu():
    """Show difficulty selection menu, return selected difficulty"""
    difficulty_names = DIFFICULTY_ORDER  # 确保顺序：EASY, MEDIUM, HARD
    selected_idx = 0  # 默认选中 EASY
    
    while True:
        display.fill(0)
        display.rect(0, 0, 128, 64, 1)
        
        # 删除标题，直接显示菜单项，往上移一点点
        # Menu items (居中显示，往上移：y=8, 21, 34)
        for i, diff_name in enumerate(difficulty_names):
            y_pos = 8 + i * 13  # y=8, 21, 34 (往上移2像素)
            prefix = "> " if i == selected_idx else "  "
            # 居中显示，不加粗
            text = prefix + diff_name
            x_pos = (128 - len(text) * 6) // 2
            display.text(text, x_pos, y_pos, 1)  # 不加粗
        
        # Instructions (底部，y=48，不动)
        draw_centered_text("Rotate/Press", 48, 1)
        
        safe_show()
        
        # 使用1步导航：向右=下，向左=上（更灵敏）
        for _ in range(10):  # 快速轮询
            nav = encoder.get_menu_navigation(steps_required=1)
            if nav == 'down':
                selected_idx = (selected_idx + 1) % len(difficulty_names)
                tone(800, 0.03)
                time.sleep(0.05)  # 缩短延迟，更灵敏
                break
            elif nav == 'up':
                selected_idx = (selected_idx - 1) % len(difficulty_names)
                tone(800, 0.03)
                time.sleep(0.05)  # 缩短延迟，更灵敏
                break
            
            # Check button
            if button.value == False:
                tone(1500, 0.1)
                while button.value == False:
                    time.sleep(0.01)
                time.sleep(0.1)
                return difficulty_names[selected_idx]
            
            time.sleep(0.002)  # 非常短的延迟，快速轮询
        
        time.sleep(0.005)  # 主要循环延迟

# ==================== BOMB EXPLOSION SPLASH ANIMATION ====================

splash_played = False

def draw_upgraded_splash():
    """炸弹炸开动画 - 爆炸效果后弹出BOMB MASTER标题"""
    global splash_played
    if splash_played:
        return
    splash_played = True
    
    # 第一阶段：炸弹出现（中心小圆点）
    center_x, center_y = 64, 32
    for frame in range(8):
        display.fill(0)
        # 炸弹（小圆点，逐渐变大）
        size = frame * 2
        if size > 0:
            display.fill_rect(center_x - size//2, center_y - size//2, size, size, 1)
        safe_show()
        if pixels:
            try:
                # 红色闪烁
                pixels.fill((min(255, frame * 30), 0, 0))
            except:
                pass
        time.sleep(0.05)
    
    # 第二阶段：爆炸效果（向外扩散的粒子）
    particles = []
    for angle in range(0, 360, 15):  # 24个方向的粒子
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
        
        # 绘制爆炸粒子
        for p in particles:
            if p['life'] > 0:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['life'] -= 1
                
                x, y = int(p['x']), int(p['y'])
                if 0 <= x < 128 and 0 <= y < 64:
                    display.fill_rect(x, y, 2, 2, 1)
        
        # 中心爆炸光
        if frame < 10:
            for i in range(3):
                size = (frame + i) * 3
                display.rect(center_x - size//2, center_y - size//2, size, size, 1)
        
        safe_show()
        
        # NeoPixel红色爆炸效果
        if pixels:
            try:
                intensity = max(0, 255 - frame * 15)
                pixels.fill((intensity, intensity // 3, 0))
            except:
                pass
        
        if frame == 5:
            tone(200, 0.1)  # 低音爆炸声
        
        time.sleep(0.04)
    
    # 第三阶段：标题弹出（从中心放大）
    title_frames = 12
    for frame in range(title_frames):
        display.fill(0)
        
        # 标题从中心放大（不加粗）
        scale = frame / title_frames
        if scale > 0.3:  # 从30%开始显示
            # 简单的放大效果（用不同大小的文字模拟）
            if scale < 0.6:
                # 小标题（不加粗）
                draw_centered_text("BOMB", 28, 1)
                draw_centered_text("MASTER", 38, 1)
            else:
                # 正常大小（不加粗）
                draw_centered_text("BOMB MASTER", 25, 1)
        
        # 残留的爆炸粒子（淡出）
        for p in particles:
            if p['life'] > 0:
                x, y = int(p['x']), int(p['y'])
                if 0 <= x < 128 and 0 <= y < 64:
                    display.fill_rect(x, y, 1, 1, 1)
        
        safe_show()
        
        # NeoPixel淡出到黄色/橙色
        if pixels:
            try:
                if frame < title_frames // 2:
                    pixels.fill((255 - frame * 20, 100 + frame * 10, 0))
                else:
                    pixels.fill((155, 200, 0))
            except:
                pass
        
        if frame == 3:
            tone(800, 0.1)  # 标题出现音效
        if frame == 8:
            tone(1200, 0.1)
        
        time.sleep(0.05)
    
    # 最终状态：标题闪烁两下（不加粗）
    for flash in range(2):
        display.fill(0)
        draw_centered_text("BOMB MASTER", 25, 1)  # 不加粗
        display.rect(0, 0, 128, 64, 1)
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 255, 0))  # 黄色
            except:
                pass
        tone(1500, 0.1)
        time.sleep(0.2)
        
        display.fill(1)
        draw_centered_text("BOMB MASTER", 25, 0)  # 不加粗
        display.rect(0, 0, 128, 64, 0)
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 100, 0))  # 橙色
            except:
                pass
        time.sleep(0.15)
    
    # 最终状态（不加粗）
    display.fill(0)
    draw_centered_text("BOMB MASTER", 25, 1)  # 不加粗
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
    """Draw game UI with centered layout - 调整间距，避免拥挤，PRESS按钮优化，加粗加大文字"""
    display.fill(0)
    display.rect(0, 0, 128, 64, 1)
    
    # Top bar: Level and Score (不加粗)
    if level is not None:
        display.text(f"L{level+1}", 5, 3, 1)
    if score is not None:
        score_str = f"S:{score}"
        display.text(score_str, 128 - len(score_str) * 6 - 5, 3, 1)
    
    # Level time progress bar (下移一点，给顶部留空间)
    if level_time_pct is not None:
        bar_width = 100
        bar_x = (128 - bar_width) // 2
        display.rect(bar_x, 13, bar_width, 4, 1)
        fill_w = int(level_time_pct * (bar_width - 2))
        fill_w = min(max(fill_w, 0), bar_width - 2)
        if fill_w > 0:
            display.fill_rect(bar_x + 1, 14, fill_w, 2, 1)
    
    # Action instruction (居中，增大间距，PRESS按钮优化，不加粗)
    y_center = 30  # 下移一点
    if target == "LEFT":
        draw_centered_text("CUT BLUE", y_center - 8)
        draw_centered_text("<< LEFT", y_center + 2)  # 不加粗
    elif target == "RIGHT":
        draw_centered_text("CUT RED", y_center - 8)
        draw_centered_text("RIGHT >>", y_center + 2)  # 不加粗
    elif target == "PRESS":
        draw_centered_text("ENTER CODE", y_center - 8)  # 上移，留更多空间
        draw_centered_text("PRESS", y_center + 2)  # 不加粗
        # Button indicator (下移，增大按钮和间距)
        btn_x = (128 - 18) // 2  # 稍微再大一点
        display.rect(btn_x, y_center + 14, 18, 14, 1)  # 更大的按钮框
        display.rect(btn_x + 1, y_center + 15, 16, 12, 1)  # 双重边框，更醒目
        if button.value == False:
            display.fill_rect(btn_x + 3, y_center + 17, 12, 10, 1)
    elif target == "SHAKE":
        draw_centered_text("DISARM!!", y_center - 8)  # 不加粗
        draw_centered_text("SHAKE IT", y_center + 2)  # 不加粗
        # Shake indicator (加粗线条)
        shake_x = (128 - 48) // 2
        display.line(shake_x, y_center + 12, shake_x + 48, y_center + 12, 1)
        display.line(shake_x, y_center + 13, shake_x + 48, y_center + 13, 1)  # 加粗
    
    # Action progress bar (for rotation actions and SHAKE, 下移到底部)
    if target in ["LEFT", "RIGHT"]:
        bar_width = 80
        bar_x = (128 - bar_width) // 2
        bar_y = 54  # 下移到底部
        display.rect(bar_x, bar_y, bar_width, 8, 1)
        fill_w = int(progress_pct * (bar_width - 2))
        fill_w = min(max(fill_w, 0), bar_width - 2)
        if fill_w > 0:
            display.fill_rect(bar_x + 1, bar_y + 1, fill_w, 6, 1)
    elif target == "SHAKE":
        # SHAKE动作也显示时间进度条
        bar_width = 80
        bar_x = (128 - bar_width) // 2
        bar_y = 54  # 下移到底部
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
    """Success animation - 更美的烟花效果，飘得更久"""
    frames = 20  # 增加帧数，让烟花飘得更久
    center_x, center_y = 64, 32
    
    # 创建更多烟花粒子
    particles = []
    for angle in range(0, 360, 10):  # 36个方向的粒子
        rad = angle * 3.14159 / 180
        speed = random.uniform(1.5, 3.0)  # 随机速度
        particles.append({
            'x': center_x,
            'y': center_y,
            'vx': __import__('math').cos(rad) * speed,
            'vy': __import__('math').sin(rad) * speed,
            'life': 25,  # 更长生命周期
            'size': random.randint(1, 2)
        })
    
    for frame in range(frames):
        display.fill(0)
        
        # 绘制烟花粒子
        for p in particles:
            if p['life'] > 0:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['life'] -= 1
                p['vy'] += 0.1  # 重力效果，让粒子下落
                
                x, y = int(p['x']), int(p['y'])
                if 0 <= x < 128 and 0 <= y < 64:
                    size = p['size']
                    display.fill_rect(x - size, y - size, size * 2 + 1, size * 2 + 1, 1)
        
        # 中心爆发效果（前几帧）
        if frame < 8:
            for i in range(3):
                size = (frame + i) * 3
                display.rect(center_x - size//2, center_y - size//2, size, size, 1)
        
        safe_show()
        
        # NeoPixel彩虹效果
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
        
        time.sleep(0.05)  # 稍慢一点，更平滑
    
    # 继续让粒子飘落（额外的帧）
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
                    size = max(1, p['size'] - frame // 5)  # 逐渐变小
                    display.fill_rect(x - size, y - size, size * 2 + 1, size * 2 + 1, 1)
        
        safe_show()
        if pixels:
            try:
                pixels.fill((255, 255, 100))  # 淡黄色
            except:
                pass
        time.sleep(0.04)
    
    # 最终淡出
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
            # 失败音效：下降音调
            tone(600 - frame * 50, 0.08)
        else:
            time.sleep(0.05)
    
    # 最终低音
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
    """Countdown before level starts - 居中显示"""
    for i in range(3, 0, -1):
        # 居中显示数字
        display.fill(0)
        display.rect(0, 0, 128, 64, 1)
        draw_centered_text(str(i), 28, 1)  # 屏幕正中央
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
    
    # GO居中显示
    display.fill(0)
    display.rect(0, 0, 128, 64, 1)
    draw_centered_text("GO!", 28, 1)  # 屏幕正中央
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
        
        # SHAKE动作的特殊处理：使用总magnitude检测 + 累计变化量
        shake_triggered = False
        shake_trigger_time = 0
        shake_hold_duration = 0.5  # 需要保持0.5秒
        last_magnitude = accel_filter.get_magnitude()  # 记录上一次magnitude
        accumulated_change = 0  # 累计变化量
        last_change_reset_time = time.monotonic()  # 上次重置累计变化量的时间
        
        while True:
            direction = encoder.get_direction()
            now = time.monotonic()
            elapsed = time.monotonic() - level_start_time
            
            # Check level time
            if elapsed >= level_time_limit:
                return False, score
            
            level_time_pct = elapsed / level_time_limit
            
            # Rotation detection
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
            
            # SHAKE detection - 优化检测：总magnitude + 单次变化量
            if target == "SHAKE":
                current_magnitude = accel_filter.get_magnitude()
                magnitude_change = abs(current_magnitude - last_magnitude)
                last_magnitude = current_magnitude
                
                # 累计变化量（在0.2秒窗口内，更灵敏）
                if now - last_change_reset_time > 0.2:  # 缩短到0.2秒窗口
                    accumulated_change = 0
                    last_change_reset_time = now
                else:
                    accumulated_change += magnitude_change
                
                # 检测条件：总magnitude超过阈值 OR 累计变化量超过阈值 OR 单次大变化
                # 根据用户数据：magnitude范围约10-16，单次变化可达4-5
                magnitude_trigger = current_magnitude > shake_threshold
                change_trigger = accumulated_change > shake_change_threshold
                big_change_trigger = magnitude_change > 4  # 单次大变化也触发（更灵敏）
                
                if magnitude_trigger or change_trigger or big_change_trigger:
                    if not shake_triggered:
                        # 第一次触发
                        shake_triggered = True
                        shake_trigger_time = now
                    else:
                        # 已经触发，检查持续时间
                        if now - shake_trigger_time >= shake_hold_duration:
                            # 时间到了，完成动作
                            done = True
                            score += 10
                            break
                # 注意：一旦触发，保持触发状态直到时间到
                
                # 计算SHAKE进度（基于触发后的时间）
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
                    progress_pct = shake_progress  # SHAKE使用时间进度
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
    # 成功音效：上升音调
    tone(1000, 0.1)
    time.sleep(0.05)
    tone(1500, 0.1)
    time.sleep(0.05)
    tone(2000, 0.15)
    time.sleep(0.2)
    
    return True, score

# ==================== MAIN GAME LOOP ====================

high_score = load_high_score()

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
                
                # Check for new high score
                if total_score > high_score:
                    high_score = total_score
                    save_high_score(high_score)
                    draw_new_high_score_animation()
                    show_message_box("HIGH SCORE!", f"{high_score}", "")
                else:
                    show_message_box("HIGH SCORE", f"{high_score}", f"Your: {total_score}")
                
                wait_for_press()
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
                
                # Check for new high score
                if total_score > high_score:
                    high_score = total_score
                    save_high_score(high_score)
                    draw_new_high_score_animation()
                    show_message_box("GAME OVER", f"New High: {high_score}", "PRESS -> MENU")
                else:
                    show_message_box("GAME OVER", f"Score: {total_score}", f"High: {high_score}")
                
                wait_for_press()
                game_active = False
        
        # Reset splash flag for next game
        splash_played = False
        
    except Exception as e:
        print("Crash:", e)
        import traceback
        traceback.print_exc()
        time.sleep(1)
