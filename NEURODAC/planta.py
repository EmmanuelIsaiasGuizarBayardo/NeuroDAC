import pygame
import sys
import random
import math 


COLOR_PALETA = [
    {'stem': (85, 53, 29), 'bud': (255, 99, 71), 'petal': (255, 182, 193), 'center': (255, 105, 180)},
    {'stem': (60, 42, 20), 'bud': (144, 238, 144), 'petal': (50, 205, 50), 'center': (34, 139, 34)},
    {'stem': (80, 50, 20), 'bud': (135, 206, 235), 'petal': (135, 206, 250), 'center': (70, 130, 180)},
    {'stem': (90, 60, 30), 'bud': (238, 232, 170), 'petal': (238, 221, 130), 'center': (205, 133, 63)},
    {'stem': (70, 40, 20), 'bud': (221, 160, 221), 'petal': (238, 130, 238), 'center': (199, 21, 133)},
]

WHITE = (245, 245, 250)
HEALTH_BG = (200, 200, 200)
HEALTH_FG = (60, 179, 113)
STAGES = 6
MAX_STEM_HEIGHT = 150
MAX_FLOWERS = 5


def crear_flor(x, ground_y, paleta):
    return {
        'x': x,
        'ground_y': ground_y,
        'attention': 50,  # Valor inicial de atención/meditación
        'threshold': 60,
        'health': 50,
        'stage': 0,
        'ticks': 0,
        'palette': paleta
    }

# Iniciar/reiniciar jardín
def iniciar_jardin(width, height):
    margin = 100
    positions = random.sample(range(margin, width - margin), MAX_FLOWERS)
    ground_y = height // 2 + 100
    flores = [crear_flor(x, ground_y, COLOR_PALETA[i % len(COLOR_PALETA)]) for i, x in enumerate(positions)]
    return flores, [], 0

# Animar semilla
def animate_seed(screen, clock, x, ground_y, completed):
    for sy in range(0, ground_y, 10):
        screen.fill(WHITE)
        for cf in completed:
            draw_flower(screen, cf)
        pygame.draw.circle(screen, (139, 69, 19), (x, sy), 8)
        pygame.display.flip()
        clock.tick(60)
    pygame.time.delay(200)


def draw_stem_and_flower(screen, f):
    x, ground_y, stage = f['x'], f['ground_y'], f['stage']
    pal = f['palette']
    t = pygame.time.get_ticks()
    stem_h = int((stage / STAGES) * MAX_STEM_HEIGHT)
    if stage > 0:
        for i in range(0, stem_h, 10):
            off = 5 * math.sin(i/15 + t/1000)
            pygame.draw.line(screen, pal['stem'], (x + off, ground_y - i), (x + off, ground_y - i - 10), 6)
    if stage == 0:
        r = 8 + 2 * math.sin(t/300)
        pygame.draw.circle(screen, pal['stem'], (x, ground_y), int(r))
        return
    top_x = x + 2 * math.sin(t/800)
    top_y = (ground_y - stem_h) + 2 * math.cos(t/800)
    if 3 <= stage < STAGES:
        size = 10 + (stage - 2) * 4 + 2 * math.sin(t/400)
        pygame.draw.ellipse(screen, pal['bud'], (top_x - size//2, top_y - size//2, size, size*1.2))
        petal_steps = stage - 3
        if petal_steps > 0:
            for i in range(petal_steps * 2):
                angle = i * (2 * math.pi / (petal_steps * 2)) + t/1000
                pr = size + 8
                px = top_x + int(pr * math.cos(angle))
                py = top_y + int(pr * math.sin(angle))
                rad = 10 + 2 * math.sin(t/500 + i)
                pygame.draw.circle(screen, pal['petal'], (px, py), int(rad))
    elif stage >= STAGES:
        size = 10 + (STAGES - 2) * 4
        total_petals = STAGES + 2
        for i in range(total_petals):
            angle = i * (2 * math.pi / total_petals) + t/1000
            pr = size + 10
            px = top_x + int(pr * math.cos(angle))
            py = top_y + int(pr * math.sin(angle))
            rad = 12 + 3 * math.sin(t/400 + i)
            surf = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, pal['petal'] + (180,), (int(rad), int(rad)), int(rad))
            screen.blit(surf, (px-int(rad), py-int(rad)))
        cr = 10 + 2 * math.sin(t/300)
        pygame.draw.circle(screen, pal['center'], (int(top_x), int(top_y)), int(cr))

# Dibuja flor sin barra individual
def draw_flower(screen, f):
    draw_stem_and_flower(screen, f)

# Dibuja texto centrado
def draw_text(screen, font, text, x, y):
    surf = font.render(text, True, (30, 30, 30))
    rect = surf.get_rect(center=(x, y))
    screen.blit(surf, rect)

# --- 1. Modificar main para aceptar el valor compartido ---
def main(shared_signal_value=None):
    pygame.init()
    WIDTH, HEIGHT = 800, 720
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("🌱 Jardín Mental 🌸")
    clock = pygame.time.Clock()
    font = pygame.font.Font(pygame.font.match_font('comicsansms'), 24)

    flores, completed, current = iniciar_jardin(WIDTH, HEIGHT)
    running = True
    
    # --- Constantes de Umbral ---
    UPPER_THRESHOLD = 55
    LOWER_THRESHOLD = 45
    CONTROL_SENSITIVITY = 1 # Puntos de atención a sumar/restar por frame

    while running:
        screen.fill(WHITE)
        f = flores[current]
        h = f['health']
        bx, by, bw, bh = 50, 20, WIDTH - 100, 15
        pygame.draw.rect(screen, HEALTH_BG, (bx, by, bw, bh), border_radius=8)
        pygame.draw.rect(screen, HEALTH_FG, (bx, by, int(bw * h / 100), bh), border_radius=8)
        draw_text(screen, font, f"Salud: {h}%", WIDTH//2, by + bh//2)

        if h == 0:
            flores, completed, current = iniciar_jardin(WIDTH, HEIGHT)
            continue

        for cf in completed:
            draw_flower(screen, cf)

        # --- 2. Lógica de Control (BCI o Teclado) ---
        if shared_signal_value is not None:
            # --- Modo BCI (Controlado por Dash) ---
            try:
                signal_val = shared_signal_value.value
                if signal_val > UPPER_THRESHOLD:
                    f['attention'] = min(100, f['attention'] + CONTROL_SENSITIVITY)
                elif signal_val < LOWER_THRESHOLD:
                    f['attention'] = max(0, f['attention'] - CONTROL_SENSITIVITY)
                # Si está entre umbrales, f['attention'] no cambia (neutral)
            except Exception:
                f['attention'] = 50 # Valor seguro en caso de error
            
            # Solo escuchar por el evento QUIT
            for event in pygame.event.get(pygame.QUIT):
                if event.type == pygame.QUIT:
                    running = False

        else:
            # --- Modo Debug (Controlado por Teclado) ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        f['attention'] = min(100, f['attention'] + 10)
                    elif event.key == pygame.K_DOWN:
                        f['attention'] = max(0, f['attention'] - 10)

        # Actualizar flor activa
        f['ticks'] += 1
        if f['ticks'] >= 60:
            f['ticks'] = 0
            if f['attention'] >= f['threshold'] and f['stage'] < STAGES:
                f['stage'] += 1
                f['health'] = min(100, f['health'] + 3)
            elif f['attention'] < f['threshold'] and f['stage'] > 0:
                f['health'] = max(0, f['health'] - 3)
                f['stage'] = max(0, f['stage'] - 1)
            else:
                delta = 7 if f['attention'] >= f['threshold'] else -3
                f['health'] = max(0, min(100, f['health'] + delta))

        if f['stage'] == STAGES:
            completed.append(f)
            next_idx = current + 1
            if next_idx < len(flores):
                flores[next_idx]['health'] = f['health']
                animate_seed(screen, clock, flores[next_idx]['x'], flores[next_idx]['ground_y'], completed)
                current = next_idx
                continue
            else:
                flores, completed, current = iniciar_jardin(WIDTH, HEIGHT)
                continue

        draw_flower(screen, f)
        draw_text(screen, font, f"Flor {current+1}/{MAX_FLOWERS}", WIDTH//2, 70)
        draw_text(screen, font, f"Atención (Meditación): {f['attention']}", WIDTH//2, 100) # Mostrar valor interno

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main() # Se ejecuta en modo debug (teclado)