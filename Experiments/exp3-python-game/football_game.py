import pygame
import serial
import serial.tools.list_ports
import sys, time, math, random, threading

# ══════════════════════════════════════════════════════════════
# ── Configuration ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
SERIAL_PORT      = "AUTO"
BAUD_RATE        = 9600
SCREEN_W         = 900
SCREEN_H         = 600
FPS              = 60
TARGET_SCORE     = 3
GK_SEND_INTERVAL = 50

# ══════════════════════════════════════════════════════════════
# ── Colour Palette ────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
GREEN_FIELD = (34,  139,  34)
DARK_GREEN  = (20,  100,  20)
WHITE       = (255, 255, 255)
BLACK       = (0,     0,   0)
YELLOW      = (255, 220,   0)
RED         = (220,  50,  50)
BLUE        = (50,  100, 220)
ORANGE      = (255, 140,   0)
GREY        = (180, 180, 180)
DARK_GREY   = (80,   80,  80)
CYAN        = (0,   200, 220)


# ══════════════════════════════════════════════════════════════
# ── Arduino Auto-Detection ────────────────────────────────────
# ══════════════════════════════════════════════════════════════
def find_arduino_port():
    for p in serial.tools.list_ports.comports():
        if any(k in p.description.lower()
               for k in ["arduino", "ch340", "usb serial", "usbserial"]):
            print(f"[Serial] Auto-detected: {p.device}  ({p.description})")
            return p.device
    for c in [f"COM{i}" for i in range(3, 15)] + \
             ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"]:
        try:
            s = serial.Serial(c, BAUD_RATE, timeout=0.5); s.close()
            print(f"[Serial] Found port: {c}")
            return c
        except Exception:
            pass
    return None


# ══════════════════════════════════════════════════════════════
# ── Serial Manager ────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
class SerialManager:
    """
    Background-thread serial wrapper.

    Receives:  "X:512,Y:512,BTN:0,BTN2:0\\n"
    Sends:     "GK:<0-180>\\n"  |  "GOAL\\n"  |  "WIN\\n"  |  "IDLE\\n"

    BTN  = joystick fire button
    BTN2 = dedicated restart button on D3        ← NEW
    """
    def __init__(self, port, baud):
        self.port, self.baud = port, baud
        self.ser      = None
        self._lock    = threading.Lock()
        self._running = False
        self._thread  = None
        self._joy_x   = 512
        self._joy_y   = 512
        self._joy_btn  = 0
        self._joy_btn2 = 0   # ← NEW: restart button

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.05)
            time.sleep(2.0)
            self.ser.reset_input_buffer()
            self._running = True
            self._thread  = threading.Thread(
                target=self._read_loop, name="SerialReader", daemon=True)
            self._thread.start()
            print(f"[Serial] Connected to {self.port} @ {self.baud} baud")
            return True
        except serial.SerialException as e:
            print(f"[Serial] Failed: {e}")
            return False

    def get_joystick(self):
        """Returns (x, y, btn, btn2)."""
        with self._lock:
            return self._joy_x, self._joy_y, self._joy_btn, self._joy_btn2

    def send_command(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                with self._lock:
                    self.ser.write((cmd + "\n").encode())
            except serial.SerialException as e:
                print(f"[Serial] Write error: {e}")

    def close(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _read_loop(self):
        buf = ""
        while self._running:
            try:
                if self.ser.in_waiting:
                    buf += self.ser.read(self.ser.in_waiting).decode("utf-8", errors="ignore")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        self._parse(line.strip())
                else:
                    time.sleep(0.005)
            except Exception as e:
                if self._running:
                    print(f"[Serial] Read error: {e}")
                time.sleep(0.1)

    def _parse(self, line):
        try:
            parts = dict(p.split(":") for p in line.split(","))
            with self._lock:
                self._joy_x    = int(parts.get("X",    512))
                self._joy_y    = int(parts.get("Y",    512))
                self._joy_btn  = int(parts.get("BTN",  0))
                self._joy_btn2 = int(parts.get("BTN2", 0))  # ← NEW
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# ── Dummy Serial (keyboard demo, no Arduino needed) ───────────
# ══════════════════════════════════════════════════════════════
class DummySerial:
    """
    Keyboard fallback:
      WASD / arrows = move
      SPACE         = charge/shoot  (BTN)
      ENTER         = restart       (BTN2)   ← NEW
    """
    def __init__(self):
        self._joy_x, self._joy_y = 512, 512
        self._joy_btn  = 0
        self._joy_btn2 = 0   # ← NEW

    def update_from_keyboard(self):
        keys = pygame.key.get_pressed()
        dx   = int(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - \
               int(keys[pygame.K_LEFT]  or keys[pygame.K_a])
        dy   = int(keys[pygame.K_DOWN]  or keys[pygame.K_s]) - \
               int(keys[pygame.K_UP]    or keys[pygame.K_w])
        self._joy_btn  = 1 if keys[pygame.K_SPACE] else 0
        self._joy_btn2 = 1 if keys[pygame.K_RETURN] else 0  # ← NEW
        self._joy_x    = 512 + dx * 400
        self._joy_y    = 512 + dy * 400

    def get_joystick(self):
        return self._joy_x, self._joy_y, self._joy_btn, self._joy_btn2

    def send_command(self, cmd):
        print(f"[DEMO] → {cmd}")

    def close(self):
        pass


# ══════════════════════════════════════════════════════════════
# ── Player ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
class Player:
    RADIUS = 18
    SPEED  = 4.5
    DEAD   = 0.12

    def __init__(self, x, y):
        self.x = float(x); self.y = float(y)
        self.vx = self.vy = 0.0
        self.facing = 0.0

    def update(self, joy_x, joy_y):
        dx = (joy_x - 512) / 512.0
        dy = (joy_y - 512) / 512.0
        if abs(dx) < self.DEAD: dx = 0.0
        if abs(dy) < self.DEAD: dy = 0.0
        self.vx = dx * self.SPEED
        self.vy = dy * self.SPEED
        self.x  = max(self.RADIUS, min(SCREEN_W - self.RADIUS, self.x + self.vx))
        self.y  = max(self.RADIUS, min(SCREEN_H - self.RADIUS, self.y + self.vy))
        if dx or dy:
            self.facing = math.degrees(math.atan2(dy, dx))

    def draw(self, surf):
        ix, iy = int(self.x), int(self.y)
        pygame.draw.circle(surf, BLUE,  (ix, iy), self.RADIUS)
        pygame.draw.circle(surf, WHITE, (ix, iy), self.RADIUS, 2)
        rad = math.radians(self.facing)
        pygame.draw.line(surf, WHITE, (ix, iy),
                         (ix + int(math.cos(rad) * self.RADIUS),
                          iy + int(math.sin(rad) * self.RADIUS)), 3)
        lbl = pygame.font.SysFont("Arial", 11, bold=True).render("P1", True, WHITE)
        surf.blit(lbl, (ix - lbl.get_width()//2, iy - lbl.get_height()//2))


# ══════════════════════════════════════════════════════════════
# ── Ball ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
class Ball:
    RADIUS   = 11
    FRICTION = 0.965
    MAX_VEL  = 14.0

    def __init__(self):
        self.reset()

    def reset(self):
        self.x = float(SCREEN_W // 2)
        self.y = float(SCREEN_H // 2)
        self.vx = self.vy = 0.0

    def kick(self, angle_deg, power):
        spd = power * self.MAX_VEL
        self.vx += math.cos(math.radians(angle_deg)) * spd
        self.vy += math.sin(math.radians(angle_deg)) * spd
        mag = math.hypot(self.vx, self.vy)
        if mag > self.MAX_VEL:
            self.vx *= self.MAX_VEL / mag
            self.vy *= self.MAX_VEL / mag

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vx *= self.FRICTION; self.vy *= self.FRICTION

        gt = SCREEN_H // 2 - 70; gb = SCREEN_H // 2 + 70
        in_goal_y = gt < self.y < gb

        if self.y - self.RADIUS < 0:
            self.y = float(self.RADIUS);            self.vy =  abs(self.vy)
        if self.y + self.RADIUS > SCREEN_H:
            self.y = float(SCREEN_H - self.RADIUS); self.vy = -abs(self.vy)
        if self.x - self.RADIUS < 0 and not in_goal_y:
            self.x = float(self.RADIUS);            self.vx =  abs(self.vx)
        if self.x + self.RADIUS > SCREEN_W and not in_goal_y:
            self.x = float(SCREEN_W - self.RADIUS); self.vx = -abs(self.vx)

    def hits(self, cx, cy, cr):
        return math.hypot(self.x - cx, self.y - cy) < (self.RADIUS + cr)

    def draw(self, surf):
        ix, iy = int(self.x), int(self.y)
        pygame.draw.circle(surf, WHITE,     (ix, iy), self.RADIUS)
        pygame.draw.circle(surf, DARK_GREY, (ix, iy), self.RADIUS, 2)
        pygame.draw.circle(surf, DARK_GREY, (ix, iy), self.RADIUS // 2, 1)


# ══════════════════════════════════════════════════════════════
# ── AI Goalkeeper ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
class GoalKeeper:
    RADIUS                = 17
    SPEED                 = 2.6
    REACTION_DELAY_FRAMES = 14
    DRIFT_RANGE           = 22
    STUMBLE_CHANCE        = 0.003
    STUMBLE_FRAMES        = 28
    GOAL_TOP              = SCREEN_H // 2 - 70
    GOAL_BOTTOM           = SCREEN_H // 2 + 70

    def __init__(self, x):
        self.x            = float(x)
        self.y            = float(SCREEN_H // 2)
        self._history     = [float(SCREEN_H // 2)] * (self.REACTION_DELAY_FRAMES + 1)
        self._hist_idx    = 0
        self._drift       = 0.0
        self._drift_timer = 0
        self._stumble     = 0

    def update(self, ball_x, ball_y, ball_vx):
        self._history[self._hist_idx % len(self._history)] = ball_y
        self._hist_idx += 1
        delayed_y = self._history[self._hist_idx % len(self._history)]

        if self._stumble > 0:
            self._stumble -= 1
            return
        if ball_x < SCREEN_W * 0.6 and random.random() < self.STUMBLE_CHANCE:
            self._stumble = self.STUMBLE_FRAMES
            return

        self._drift_timer -= 1
        if self._drift_timer <= 0:
            self._drift       = random.uniform(-self.DRIFT_RANGE, self.DRIFT_RANGE)
            self._drift_timer = random.randint(25, 55)

        if ball_vx > 1.5 and ball_x > SCREEN_W * 0.55:
            target_y = delayed_y + self._drift
        else:
            target_y = float(SCREEN_H // 2) + self._drift * 0.4

        target_y = max(self.GOAL_TOP  + self.RADIUS,
                       min(self.GOAL_BOTTOM - self.RADIUS, target_y))
        diff = target_y - self.y
        self.y += min(abs(diff), self.SPEED) * (1 if diff > 0 else -1)

    def servo_angle(self):
        span    = self.GOAL_BOTTOM - self.GOAL_TOP
        clamped = max(self.GOAL_TOP, min(self.GOAL_BOTTOM, self.y))
        return int((clamped - self.GOAL_TOP) / span * 180)

    def draw(self, surf):
        ix, iy = int(self.x), int(self.y)
        colour = RED if self._stumble > 0 else ORANGE
        pygame.draw.circle(surf, colour, (ix, iy), self.RADIUS)
        pygame.draw.circle(surf, WHITE,  (ix, iy), self.RADIUS, 2)
        lbl = pygame.font.SysFont("Arial", 11, bold=True).render("GK", True, WHITE)
        surf.blit(lbl, (ix - lbl.get_width()//2, iy - lbl.get_height()//2))


# ══════════════════════════════════════════════════════════════
# ── Main Game ─────────────────────────────────════════════════
# ══════════════════════════════════════════════════════════════
class FootballGame:
    GOAL_W   = 140
    SHOOT_CD = 800

    def __init__(self, serial_mgr):
        self.serial       = serial_mgr
        self.player       = Player(SCREEN_W // 4, SCREEN_H // 2)
        self.ball         = Ball()
        self.gk           = GoalKeeper(float(SCREEN_W - 32))
        self.score        = 0
        self.state        = "PLAYING"
        self.state_timer  = 0
        self.last_shoot   = 0
        self.power        = 0.0
        self.charging     = False
        self.flash_alpha  = 0
        self.last_gk_send = 0

        # ── BTN2 edge-detection: only restart on PRESS, not hold ──
        self._prev_btn2   = 0   # ← NEW

        self.f_big   = pygame.font.SysFont("Arial", 54, bold=True)
        self.f_med   = pygame.font.SysFont("Arial", 32, bold=True)
        self.f_small = pygame.font.SysFont("Arial", 20)

    # ── Update ──────────────────────────────────────────────
    def update(self):
        joy_x, joy_y, joy_btn, joy_btn2 = self.serial.get_joystick()
        now = pygame.time.get_ticks()

        # ── Detect BTN2 rising edge (press, not hold) ─────────
        btn2_pressed = (joy_btn2 == 1 and self._prev_btn2 == 0)
        self._prev_btn2 = joy_btn2

        if self.state == "PLAYING":
            self._update_playing(joy_x, joy_y, joy_btn, now)
        elif self.state == "GOAL":
            if now - self.state_timer > 2200:
                self._reset_round()
        elif self.state == "WIN":
            # Physical restart button triggers new game
            if btn2_pressed:
                self.__init__(self.serial)
                return

        self.flash_alpha = max(0, self.flash_alpha - 7)

        if now - self.last_gk_send >= GK_SEND_INTERVAL:
            self.serial.send_command(f"GK:{self.gk.servo_angle()}")
            self.last_gk_send = now

    def _update_playing(self, joy_x, joy_y, joy_btn, now):
        self.player.update(joy_x, joy_y)
        self.ball.update()
        self.gk.update(self.ball.x, self.ball.y, self.ball.vx)

        if joy_btn:
            self.charging = True
            self.power    = min(1.0, self.power + 0.025)
        else:
            if self.charging and (now - self.last_shoot > self.SHOOT_CD):
                if self.ball.hits(self.player.x, self.player.y, Player.RADIUS + 14):
                    self.ball.kick(self.player.facing, max(0.3, self.power))
                    self.last_shoot = now
            self.charging = False
            self.power    = max(0.0, self.power - 0.03)

        if self.ball.hits(self.player.x, self.player.y, Player.RADIUS + Ball.RADIUS + 1):
            a = math.atan2(self.ball.y - self.player.y, self.ball.x - self.player.x)
            self.ball.vx += math.cos(a) * 3.5
            self.ball.vy += math.sin(a) * 3.5

        if self.ball.hits(self.gk.x, self.gk.y, GoalKeeper.RADIUS + Ball.RADIUS):
            a   = math.atan2(self.ball.y - self.gk.y, self.ball.x - self.gk.x)
            spd = max(math.hypot(self.ball.vx, self.ball.vy), 5.0)
            self.ball.vx = math.cos(a) * spd
            self.ball.vy = math.sin(a) * spd

        gt = SCREEN_H // 2 - self.GOAL_W // 2
        gb = SCREEN_H // 2 + self.GOAL_W // 2
        if self.ball.x + Ball.RADIUS >= SCREEN_W and gt < self.ball.y < gb:
            self.score      += 1
            self.flash_alpha = 255
            self.state_timer = now
            if self.score >= TARGET_SCORE:
                self.state = "WIN"
                self.serial.send_command("WIN")
            else:
                self.state = "GOAL"
                self.serial.send_command("GOAL")

    def _reset_round(self):
        self.ball.reset()
        self.player.x = float(SCREEN_W // 4)
        self.player.y = float(SCREEN_H // 2)
        self.state    = "PLAYING"

    # ── Draw ────────────────────────────────────────────────
    def draw(self, surf):
        self._draw_field(surf)
        self.ball.draw(surf)
        self.player.draw(surf)
        self.gk.draw(surf)
        self._draw_power_bar(surf)
        self._draw_hud(surf)
        self._draw_flash(surf)
        self._draw_overlays(surf)

    def _draw_field(self, surf):
        surf.fill(GREEN_FIELD)
        pygame.draw.rect(surf,   DARK_GREEN, (5, 5, SCREEN_W-10, SCREEN_H-10), 2)
        pygame.draw.line(surf,   DARK_GREEN, (SCREEN_W//2, 5), (SCREEN_W//2, SCREEN_H-5), 2)
        pygame.draw.circle(surf, DARK_GREEN, (SCREEN_W//2, SCREEN_H//2), 80, 2)
        pygame.draw.circle(surf, DARK_GREEN, (SCREEN_W//2, SCREEN_H//2), 5)
        gt = SCREEN_H//2 - self.GOAL_W//2
        gb = SCREEN_H//2 + self.GOAL_W//2
        pygame.draw.rect(surf, WHITE,      (0,           gt, 28, self.GOAL_W), 3)
        pygame.draw.rect(surf, YELLOW,     (SCREEN_W-28, gt, 28, self.GOAL_W), 3)
        pygame.draw.rect(surf, DARK_GREEN, (SCREEN_W-90, gt-20, 90, self.GOAL_W+40), 1)

    def _draw_hud(self, surf):
        s = self.f_med.render(f"⚽  {self.score}  /  {TARGET_SCORE}", True, WHITE)
        surf.blit(s, (SCREEN_W//2 - s.get_width()//2, 8))
        h = self.f_small.render(
            "Hold BTN to charge  |  Release near ball to kick  |  ESC = quit",
            True, GREY)
        surf.blit(h, (SCREEN_W//2 - h.get_width()//2, SCREEN_H - 24))

    def _draw_power_bar(self, surf):
        bw, bh, bx, by = 170, 20, SCREEN_W - 180, 10
        pygame.draw.rect(surf, DARK_GREY, (bx, by, bw, bh), border_radius=4)
        fw = int(bw * self.power)
        if fw > 0:
            r = int(self.power * 230)
            g = int((1.0 - self.power) * 200) + 55
            pygame.draw.rect(surf, (r, g, 40), (bx, by, fw, bh), border_radius=4)
        pygame.draw.rect(surf, WHITE, (bx, by, bw, bh), 2, border_radius=4)
        lbl = self.f_small.render("POWER", True, WHITE)
        surf.blit(lbl, (bx + bw//2 - lbl.get_width()//2, by + 2))

    def _draw_flash(self, surf):
        if self.flash_alpha > 0:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((255, 255, 0, self.flash_alpha))
            surf.blit(ov, (0, 0))

    def _draw_overlays(self, surf):
        if self.state == "GOAL":
            self._text(surf, "GOAL!",
                       self.f_big, YELLOW, -40)
            self._text(surf, f"Score: {self.score} / {TARGET_SCORE}",
                       self.f_med, WHITE,  30)
        if self.state == "WIN":
            self._text(surf, "YOU WIN!",                   self.f_big, YELLOW, -70)
            self._text(surf, f"Final: {self.score} goals", self.f_med, WHITE,  -10)
            # Updated prompt: physical button instead of keyboard key
            self._text(surf, "Press the RESTART button to play again",
                       self.f_med, CYAN, 50)

    def _text(self, surf, text, font, colour, oy=0):
        sh = font.render(text, True, BLACK)
        s  = font.render(text, True, colour)
        x  = (SCREEN_W - s.get_width())  // 2
        y  = (SCREEN_H - s.get_height()) // 2 + oy
        surf.blit(sh, (x+2, y+2)); surf.blit(s, (x, y))

    def handle_event(self, event):
        # R key removed — restart is now hardware-only (BTN2 / D3)
        pass


# ══════════════════════════════════════════════════════════════
# ── Connecting Screen ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
def draw_connecting(surf):
    surf.fill((12, 12, 28))
    items = [
        (pygame.font.SysFont("Arial", 50, bold=True),
         "JOYSTICK FOOTBALL", YELLOW, -120),
        (pygame.font.SysFont("Arial", 26),
         "Searching for Arduino…", WHITE, 10),
        (pygame.font.SysFont("Arial", 19),
         "Connect Arduino via USB and upload the sketch.", GREY, 55),
        (pygame.font.SysFont("Arial", 17),
         "(Runs in DEMO / keyboard mode if no Arduino is found)", DARK_GREY, 90),
    ]
    for font, text, col, oy in items:
        s = font.render(text, True, col)
        surf.blit(s, (SCREEN_W//2 - s.get_width()//2,
                      SCREEN_H//2 - s.get_height()//2 + oy))
    pygame.display.flip()


# ══════════════════════════════════════════════════════════════
# ── Entry Point ───────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("⚽  Joystick Football  –  Arduino Edition")
    clock = pygame.time.Clock()

    draw_connecting(screen)
    pygame.event.pump()

    port = SERIAL_PORT if SERIAL_PORT != "AUTO" else find_arduino_port()
    if port:
        mgr = SerialManager(port, BAUD_RATE)
        serial_mgr = mgr if mgr.connect() else DummySerial()
        if isinstance(serial_mgr, DummySerial):
            print("[WARNING] Serial failed – DEMO mode (keyboard)")
    else:
        print("[WARNING] No Arduino found – DEMO mode (keyboard)")
        serial_mgr = DummySerial()

    game = FootballGame(serial_mgr)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            game.handle_event(event)

        if isinstance(serial_mgr, DummySerial):
            serial_mgr.update_from_keyboard()

        game.update()
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    serial_mgr.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()

