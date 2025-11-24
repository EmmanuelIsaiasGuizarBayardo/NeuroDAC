import pygame
import sys
import random
import time
import os

# --- Configuración inicial ---
pygame.init()
WIDTH, HEIGHT = 600, 800
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Carrera de Coches Mental")
CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 36)

# --- Parámetros de juego ---
LANE_COUNT = 3
LANE_WIDTH = WIDTH // LANE_COUNT
CAR_WIDTH, CAR_HEIGHT = 100, 100
OBST_WIDTH, OBST_HEIGHT = 100, 90 
BASE_SPEED = 5.0
ATTENTION_THRESHOLD = 50
ATTENTION_STEP = 5 
MIN_ATT, MAX_ATT = 0, 200
PIXELS_PER_METER = 20
PENALTY_SPEED_LOSS = 3.0
PENALTY_RECOVERY_RATE = 1.0

# --- Carga de imágenes ---
BASE_DIR = os.path.dirname(__file__)
ASSETS_PATH = os.path.join(BASE_DIR) 

try:
    car_image_path = os.path.join(ASSETS_PATH, "assets/car.png")
    CAR_IMAGE = pygame.image.load(car_image_path).convert_alpha()
    CAR_IMAGE = pygame.transform.scale(CAR_IMAGE, (CAR_WIDTH, CAR_HEIGHT))

    OBSTACLE_FILENAMES = ["assets/obstacle1.png", "assets/obstacle2.png", "assets/obstacle3.png"]
    OBST_IMAGES = []
    for fname in OBSTACLE_FILENAMES:
        obstacle_path = os.path.join(ASSETS_PATH, fname)
        img = pygame.image.load(obstacle_path).convert_alpha()
        img = pygame.transform.scale(img, (OBST_WIDTH, OBST_HEIGHT))
        OBST_IMAGES.append(img)

except pygame.error as e:
    print(f"Error al cargar una imagen desde la ruta: {ASSETS_PATH}")
    print(f"Error específico de Pygame: {e}")
    sys.exit()

class Car:
    def __init__(self, lane):
        self.lane = lane
        self.rect = pygame.Rect(
            lane * LANE_WIDTH + (LANE_WIDTH - CAR_WIDTH)//2,
            HEIGHT - CAR_HEIGHT,
            CAR_WIDTH, CAR_HEIGHT
        )
        self.image = CAR_IMAGE

    def draw(self):
        SCREEN.blit(self.image, (self.rect.x, self.rect.y))

    def move_lane(self, dir):
        self.lane = max(0, min(LANE_COUNT-1, self.lane + dir))
        self.rect.x = self.lane * LANE_WIDTH + (LANE_WIDTH - CAR_WIDTH)//2

class Obstacle:
    def __init__(self, lane):
        self.lane = lane
        self.rect = pygame.Rect(
            lane * LANE_WIDTH + (LANE_WIDTH - OBST_WIDTH)//2,
            -OBST_HEIGHT-20,
            OBST_WIDTH, OBST_HEIGHT-20
        )
        self.image = random.choice(OBST_IMAGES) 

    def update(self, speed, dt):
        self.rect.y += speed * PIXELS_PER_METER * dt

    def draw(self):
        SCREEN.blit(self.image, (self.rect.x, self.rect.y))

# --- 1. Modificar main para aceptar el valor compartido ---
def main(shared_signal_value=None):
    attention = 50 # Valor inicial
    distance = 0.0
    last_obst_dist = 0.0
    obstacles = []
    collision_penalty = 0.0

    player = Car(lane=1)
    ghost = Car(lane=1)
    ghost_distance = 0.0
    ghost_speed = BASE_SPEED + 40

    total_time = 0.0
    good_att_time = 0.0

    # --- Constantes de Umbral ---
    UPPER_THRESHOLD = 35
    LOWER_THRESHOLD = 25
    # Sensibilidad (cuánto cambia la 'attention' por frame)
    CONTROL_SENSITIVITY = ATTENTION_STEP // 3 # Un poco más suave que el teclado

    start_time = time.time()
    running = True
    while running:
        dt = CLOCK.tick(60) / 1000.0
        total_time += dt

        # --- 2. Lógica de Control BCI (Vertical) ---
        if shared_signal_value is not None:
            # --- Modo BCI ---
            try:
                signal_val = shared_signal_value.value
                if signal_val > UPPER_THRESHOLD:
                    attention = min(MAX_ATT, attention + CONTROL_SENSITIVITY) # Simula 'W'
                elif signal_val < LOWER_THRESHOLD:
                    attention = max(MIN_ATT, attention - CONTROL_SENSITIVITY) # Simula 'S'
            except Exception:
                attention = 50 # Valor seguro
        
        # --- 3. Lógica de Eventos de Teclado (Horizontal y Salir) ---
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.KEYDOWN:
                # --- Controles de depuración (solo si se ejecuta directo) ---
                if shared_signal_value is None:
                    if e.key == pygame.K_w:
                        attention = min(MAX_ATT, attention + ATTENTION_STEP)
                    elif e.key == pygame.K_s:
                        attention = max(MIN_ATT, attention - ATTENTION_STEP)
                
                # --- Controles laterales SIEMPRE ACTIVOS ---
                if e.key == pygame.K_LEFT:
                    player.move_lane(-1)
                elif e.key == pygame.K_RIGHT:
                    player.move_lane(1)

        # Cálculo de velocidad con penalización 
        extra_speed = max(0, attention*0.5 - ATTENTION_THRESHOLD)
        speed = BASE_SPEED + extra_speed - collision_penalty
        collision_penalty = max(0.0, collision_penalty - PENALTY_RECOVERY_RATE * dt)

        if attention > ATTENTION_THRESHOLD:
            good_att_time += dt

        distance += speed * dt
        ghost_distance += ghost_speed * dt

        if distance - last_obst_dist >= 10.0:
            obstacles.append(Obstacle(random.randrange(LANE_COUNT)))
            last_obst_dist = distance

        for obst in obstacles[:]:
            obst.update(speed, dt)
            if obst.rect.colliderect(player.rect):
                collision_penalty += PENALTY_SPEED_LOSS
                obstacles.remove(obst)
            elif obst.rect.y > HEIGHT:
                obstacles.remove(obst)

        
        SCREEN.fill((30,30,30))
        for i in range(1, LANE_COUNT):
            x = i * LANE_WIDTH
            pygame.draw.line(SCREEN, (50,50,50), (x,0), (x,HEIGHT), 3)

        ghost.rect.y = HEIGHT - CAR_HEIGHT - 20 - int((ghost_distance - distance) * PIXELS_PER_METER)
        ghost.draw()
        player.draw()
        for obst in obstacles:
            obst.draw()

        hud = [
            f"Distancia: {distance:.1f} m",
            f"Atención: {attention}",
            f"Velocidad: {speed:.1f} m/s",
            f"Fantasma: {ghost_distance:.1f} m"
        ]
        for i, txt in enumerate(hud):
            surf = FONT.render(txt, True, (255,255,255))
            SCREEN.blit(surf, (10, 10 + 30*i))

        pygame.display.flip()

    end_time = time.time()
    pct_good = good_att_time / total_time * 100
    print(f"¡Juego terminado! Tiempo: {total_time:.2f} s")
    print(f"% tiempo con atención > umbral: {pct_good:.1f}%")
    pygame.quit()

if __name__ == "__main__":
    main() # Se ejecuta en modo debug (teclado)