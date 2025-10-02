import sys
import math
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QPixmap
import random
import time

# Constants
GRAVITY = 0.8
BOUNCE = 0.6
FRICTION = 0.99
GROUND_MARGIN = 35 # how far from bottom of screen to "bounce"
FPS = 60

class ScreenBuddy(QLabel):
    def __init__(self, image_path):
        super().__init__()
        
        pixmap = QPixmap(image_path)

        scale_factor = 3.0
        def load_scaled(path):
            pm = QPixmap(path)
            return pm.scaled(
                pm.width() * scale_factor,
                pm.height() * scale_factor,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        scaled_pixmap = pixmap.scaled(
            pixmap.width() * scale_factor,
            pixmap.height() * scale_factor,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.frames = {
            "idle": [
                load_scaled("assets/idle1.png"), 
                load_scaled("assets/idle2.png")
            ],
            "blink": [load_scaled("assets/blink.png")],
            "walk": [
                load_scaled("assets/walk1.png"),
                load_scaled("assets/walk2.png")
            ],
            "drag": [load_scaled("assets/grab.png")]
        }

        # Set initial pixmap
        self.state = "idle"
        self.frame_index = 0
        self.setPixmap(self.frames["idle"][0])

        # Window Flags
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        # --- Animation Control ---
        self.last_idle_swap = time.time()
        self.idle_swap_interval = 2.0  # seconds between idle frame swaps

        # Periodically choose new action
        self.next_action_timer = QTimer()
        self.next_action_timer.timeout.connect(self.choose_next_action)
        self.next_action_timer.start(8000)  # every ~8s, maybe change action

        # Physics
        self.vx = 0
        self.vy = 0
        self.dragging = False
        self.last_mouse_pos = None
        self.drag_history = []
        self.throw_multiplier = 5

        # Timer for update loop
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(int(1000 / FPS))

        # Position roughly center of screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() // 2, screen.height() // 2)

        self.show()

     # --- Main Loop ---
    def update_loop(self):
        self.update_physics()
        self.animate()

    # --- Mouse Events ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_mouse_pos = event.globalPosition().toPoint()
            self.vx = 0
            self.vy = 0
            self.set_state("drag")

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = event.globalPosition().toPoint()
            delta = new_pos - self.last_mouse_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.last_mouse_pos = new_pos
            # Track velocity (for throwing)
            self.drag_history.append((delta.x(), delta.y()))
            if len(self.drag_history) > 5:
                self.drag_history.pop(0)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            if self.drag_history:
                avg_dx = sum(dx for dx, _ in self.drag_history) / len(self.drag_history)
                avg_dy = sum(dy for _, dy in self.drag_history) / len(self.drag_history)
                self.vx = avg_dx * self.throw_multiplier
                self.vy = avg_dy * self.throw_multiplier
        self.drag_history.clear()
        self.set_state("idle")

    # --- Physics Loop ---
    def update_physics(self):
        if self.dragging:
            return  # don't apply physics while dragging

        # Get screen dimensions
        # screen_geom = QApplication.primaryScreen().geometry()
        # screen_w, screen_h = screen_geom.width(), screen_geom.height()
        desktop = QApplication.instance().primaryScreen().virtualGeometry()
        screen_x = desktop.x()
        screen_y = desktop.y()
        screen_w = desktop.width()
        screen_h = desktop.height()

        # Apply gravity
        self.vy += GRAVITY

        # Update position
        new_x = self.x() + self.vx
        new_y = self.y() + self.vy

        # Bounce off floor
        bottom_limit = screen_h - self.height() - GROUND_MARGIN
        if new_y > bottom_limit:
            new_y = bottom_limit
            self.vy = -self.vy * BOUNCE
            self.vx *= FRICTION
            # Stop tiny bounces
            if abs(self.vy) < 1:
                self.vy = 0
            if abs(self.vx) < 0.5:
                self.vx = 0

        # Bounce off
        if new_x < 0:
            new_x = 0
            self.vx = -self.vx * BOUNCE
        elif new_x + self.width() > screen_w:
            new_x = screen_w - self.width()
            self.vx = -self.vx * BOUNCE

        # Move sprite
        self.move(int(new_x), int(new_y))

        # Apply friction
        self.vx *= FRICTION

    # --- Animation ---
    def animate(self):
        """Animate based on current state"""
        now = time.time()

        # --- IDLE ---
        if self.state == "idle" and self.is_resting():
            # Swap idle frames occasionally
            if now - self.last_idle_swap > self.idle_swap_interval:
                self.frame_index = (self.frame_index + 1) % len(self.frames["idle"])
                self.setPixmap(self.frames["idle"][self.frame_index])
                self.last_idle_swap = now

        # --- BLINK ---
        elif self.state == "blink":
            self.setPixmap(self.frames["blink"][0])

        # --- WALK ---
        elif self.state == "walk":
            # Toggle frames quickly and move
            if now - self.last_idle_swap > 0.25:  # Faster step rate
                self.frame_index = (self.frame_index + 1) % len(self.frames["walk"])
                self.setPixmap(self.frames["walk"][self.frame_index])
                self.last_idle_swap = now

                step = 8 if self.walk_dir == "right" else -8
                self.move(self.x() + step, self.y())

                # Stop walking when near screen edge
                desktop = QApplication.instance().primaryScreen().virtualGeometry()
                screen_x = desktop.x()
                screen_w = desktop.width()
                if self.x() <= screen_x or self.x() + self.width() >= screen_x + screen_w:
                    self.set_state("idle")
    
    def choose_next_action(self):
        """Occasionally switch to blink or walk if resting"""
        if self.dragging or not self.is_resting():
            return

        action = random.choice(["idle", "idle", "blink", "walk"])
        self.set_state(action)

        if action == "blink":
            QTimer.singleShot(500, lambda: self.set_state("idle"))
        elif action == "walk":
            self.walk_dir = random.choice(["left", "right"])
            QTimer.singleShot(2000, lambda: self.set_state("idle"))

    def set_state(self, new_state):
        self.state = new_state
        self.frame_index = 0

        if new_state in self.frames:
            frame = self.frames[new_state][0]

            # Preserve bottom position
            old_bottom = self.y() + self.height()

            # Resize label to pixmap
            self.resize(frame.size())
            self.setPixmap(frame)

            # Keep feet planted
            new_y = old_bottom - self.height()
            self.move(self.x(), new_y)



    def is_resting(self):
        return (
            not self.dragging
            and abs(self.vx) < 0.5
            and abs(self.vy) < 0.5
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    buddy = ScreenBuddy("assets/idle1.png")
    sys.exit(app.exec())
