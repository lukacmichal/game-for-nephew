import pygame
import sys
import time
import random
import os
from collections import deque

# --- Asset file path fix ---
# Ensures the script can find image files when run from different directories
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
except NameError: 
    pass

# --- Initialize Pygame ---
pygame.init()

# --- Game window and map constants ---
BLOCK_SIZE = 16
MAP_WIDTH_IN_BLOCKS = 63
MAP_HEIGHT_IN_BLOCKS = 47
WINDOW_WIDTH = MAP_WIDTH_IN_BLOCKS * BLOCK_SIZE
WINDOW_HEIGHT = MAP_HEIGHT_IN_BLOCKS * BLOCK_SIZE
WINDOW = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Chase Game 1024x768 | Final Corrected Version")

# --- Load and scale game assets ---
try:
    GROUND_IMG = pygame.transform.scale(pygame.image.load("zem.png"), (BLOCK_SIZE, BLOCK_SIZE))
    WALL_IMG = pygame.transform.scale(pygame.image.load("mur.png"), (BLOCK_SIZE, BLOCK_SIZE))
    TREASURE_IMG = pygame.transform.scale(pygame.image.load("poklad.png"), (BLOCK_SIZE, BLOCK_SIZE))
    PLAYER1_IMG = pygame.transform.scale(pygame.image.load("hrac1.png"), (BLOCK_SIZE, BLOCK_SIZE))
    PLAYER2_IMG = pygame.transform.scale(pygame.image.load("hrac2.png"), (BLOCK_SIZE, BLOCK_SIZE))
except pygame.error as e: 
    print(f"Error loading image: {e}")
    sys.exit()

# --- Create visual effects for special tiles ---
RETURN_TRAP_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE)); RETURN_TRAP_IMG.fill((227, 26, 26))
STOP_TRAP_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE)); STOP_TRAP_IMG.fill((34, 177, 76))
SLOW_TRAP_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE)); SLOW_TRAP_IMG.fill((66, 135, 245))
HASTE_BUTTON_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE)); HASTE_BUTTON_IMG.fill((255, 242, 0))
SWAP_PLAYERS_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE)); SWAP_PLAYERS_IMG.fill((163, 73, 164))
TELEPORT_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE))
pygame.draw.rect(TELEPORT_IMG, (255, 255, 255), (0, 0, BLOCK_SIZE, BLOCK_SIZE))
pygame.draw.rect(TELEPORT_IMG, (0, 128, 255), (2, 2, BLOCK_SIZE - 4, BLOCK_SIZE - 4))
STATUS_EFFECT_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
STATUS_EFFECT_IMG.fill((173, 216, 230, 180)) # Visual overlay for active status effects
COOLDOWN_EFFECT_IMG = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
COOLDOWN_EFFECT_IMG.fill((128, 128, 128, 200)) # Visual overlay for cooldowns

# --- Maze generation function ---
def generate_maze(width, height):
    maze = [['M' for _ in range(width)] for _ in range(height)]
    cell_width, cell_height = (width - 1) // 2, (height - 1) // 2
    visited = [[False for _ in range(cell_width)] for _ in range(cell_height)]
    def carve_path(cx, cy):
        visited[cy][cx] = True; maze[cy*2+1][cx*2+1] = '.'; neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]; random.shuffle(neighbors)
        for dx, dy in neighbors:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < cell_width and 0 <= ny < cell_height and not visited[ny][nx]:
                maze[cy*2+1 + dy][cx*2+1 + dx] = '.'; carve_path(nx, ny)
    carve_path(random.randint(0, cell_width-1), random.randint(0, cell_height-1))
    player1_pos, player2_pos = (1, 1), (width - 2, height - 2)
    maze[player1_pos[1]][player1_pos[0]] = '1'; maze[player2_pos[1]][player2_pos[0]] = '2'
    empty_tiles = [(x, y) for y, row in enumerate(maze) for x, block in enumerate(row) if block == '.' and (x,y) not in [player1_pos, player2_pos]]
    random.shuffle(empty_tiles)
    special_item_count = (width * height) // 70
    for _ in range(special_item_count):
        if not empty_tiles: break
        x, y = empty_tiles.pop(); maze[y][x] = random.choice(['R', 'G', 'B', 'H', 'H', 'S'])
    for _ in range(5):
        if not empty_tiles: break
        x, y = empty_tiles.pop(); maze[y][x] = 'T'
    return ["".join(row) for row in maze], empty_tiles

# --- Sprite Classes ---
class TeleportPad(pygame.sprite.Sprite):
    def __init__(self, pos):
        super().__init__(); self.image = TELEPORT_IMG
        self.rect = self.image.get_rect(topleft=pos); self.destination = None
    def link_partner(self, partner_pad): self.destination = partner_pad.rect.topleft

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, image):
        super().__init__(); self.image = image
        self.position = pygame.math.Vector2(x, y)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.start_pos = (x, y); self.score = 0; self.last_direction = (0, 1)
        self.movement_speed = 8.0; self.is_moving = False; self.target_pos = self.position.copy()
        self.is_stopped, self.stop_time = False, 0
        self.is_slowed, self.slow_time = False, 0; self.is_hasted, self.haste_time = False, 0
        self.can_destroy_wall, self.wall_destroy_cooldown = True, 0
        self.can_teleport, self.teleport_cooldown = True, 0
        
    def start_movement(self, dx, dy, walls):
        # CORRECTED LOGIC: Store the intended direction on every key press
        if dx or dy:
            self.last_direction = (dx, dy)

        if self.is_moving or self.is_stopped:
            return
        
        new_x = self.position.x + (dx * BLOCK_SIZE); new_y = self.position.y + (dy * BLOCK_SIZE)
        test_rect = pygame.Rect(new_x, new_y, BLOCK_SIZE, BLOCK_SIZE)
        
        collision = any(wall.rect.colliderect(test_rect) for wall in walls)
        
        if not collision:
            self.target_pos = pygame.math.Vector2(new_x, new_y)
            self.is_moving = True

    def update(self, dt):
        if self.is_moving:
            speed = self.movement_speed
            if self.is_hasted: speed *= 1.75
            if self.is_slowed: speed *= 0.5
            self.position = self.position.lerp(self.target_pos, speed * dt)
            if self.position.distance_to(self.target_pos) < 1.0:
                self.position = self.target_pos.copy(); self.is_moving = False
        self.rect.x = round(self.position.x); self.rect.y = round(self.position.y)
        self.update_status_effects()

    def destroy_wall(self, walls):
        if self.is_stopped or not self.can_destroy_wall: return
        # Logic uses the correctly updated 'last_direction'
        target_x = self.rect.centerx + self.last_direction[0] * BLOCK_SIZE
        target_y = self.rect.centery + self.last_direction[1] * BLOCK_SIZE
        for wall in walls:
            if wall.rect.collidepoint(target_x, target_y):
                wall.kill(); self.can_destroy_wall = False
                self.wall_destroy_cooldown = time.time() + 10; break
                
    def teleport(self, destination):
        if not self.can_teleport: return False
        self.position.x, self.position.y = destination[0], destination[1]
        self.target_pos = self.position.copy(); self.is_moving = False
        self.rect.topleft = destination; self.can_teleport = False
        self.teleport_cooldown = time.time() + 1.5; return True
        
    def update_status_effects(self):
        current_time = time.time()
        if self.is_stopped and current_time > self.stop_time: self.is_stopped = False
        if self.is_slowed and current_time > self.slow_time: self.is_slowed = False
        if self.is_hasted and current_time > self.haste_time: self.is_hasted = False
        if not self.can_destroy_wall and current_time > self.wall_destroy_cooldown: self.can_destroy_wall = True
        if not self.can_teleport and current_time > self.teleport_cooldown: self.can_teleport = True

# --- World creation from maze layout ---
def create_world_from_layout(layout):
    player1_start, player2_start = None, None
    for y, row in enumerate(layout):
        for x, block in enumerate(row):
            pos = (x * BLOCK_SIZE, y * BLOCK_SIZE); sprite = pygame.sprite.Sprite()
            sprite.rect = pygame.Rect(pos, (BLOCK_SIZE, BLOCK_SIZE))
            if block == 'M': sprite.image = WALL_IMG; walls.add(sprite)
            elif block == '1': player1_start = pos
            elif block == '2': player2_start = pos
            elif block == 'T': sprite.image = TREASURE_IMG; treasures.add(sprite)
            elif block == 'R': sprite.image = RETURN_TRAP_IMG; return_traps.add(sprite)
            elif block == 'G': sprite.image = STOP_TRAP_IMG; stop_traps.add(sprite)
            elif block == 'B': sprite.image = SLOW_TRAP_IMG; slow_traps.add(sprite)
            elif block == 'H': sprite.image = HASTE_BUTTON_IMG; haste_buttons.add(sprite)
            elif block == 'S': sprite.image = SWAP_PLAYERS_IMG; swap_pads.add(sprite)
    return player1_start, player2_start

# --- Initialize sprite groups ---
players = pygame.sprite.Group(); walls = pygame.sprite.Group(); treasures = pygame.sprite.Group()
return_traps = pygame.sprite.Group(); stop_traps = pygame.sprite.Group()
slow_traps = pygame.sprite.Group(); haste_buttons = pygame.sprite.Group()
swap_pads = pygame.sprite.Group(); teleport_pads = pygame.sprite.Group()

# --- Generate maze and create world ---
maze_layout, remaining_empty_tiles = generate_maze(MAP_WIDTH_IN_BLOCKS, MAP_HEIGHT_IN_BLOCKS)
player1_pos, player2_pos = create_world_from_layout(maze_layout)
if len(remaining_empty_tiles) >= 12:
    teleport_positions = random.sample(remaining_empty_tiles, 12)
    pads = [TeleportPad((x * BLOCK_SIZE, y * BLOCK_SIZE)) for x, y in teleport_positions]
    random.shuffle(pads)
    for i in range(0, 12, 2): pads[i].link_partner(pads[i+1]); pads[i+1].link_partner(pads[i])
    teleport_pads.add(pads)
if player1_pos and player2_pos:
    player1 = Player(player1_pos[0], player1_pos[1], PLAYER1_IMG)
    player2 = Player(player2_pos[0], player2_pos[1], PLAYER2_IMG)
    players.add(player1, player2)
else: print("Error: Player start positions not found in maze!"); sys.exit()

# --- Initialize fonts ---
SCORE_FONT = pygame.font.Font(None, 36); WINNER_FONT = pygame.font.Font(None, 120)
def display_winner(winner_text):
    text_surf = WINNER_FONT.render(winner_text, True, (255, 215, 0))
    text_rect = text_surf.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2))
    bg_rect = text_rect.inflate(20, 20)
    pygame.draw.rect(WINDOW, (0, 0, 0), bg_rect); WINDOW.blit(text_surf, text_rect); pygame.display.flip(); time.sleep(5)

# --- Main Game Loop ---
winner = None; clock = pygame.time.Clock()
while True:
    dt = clock.tick(60) / 1000.0
    # The event loop is only for single-press actions now (like quitting)
    for event in pygame.event.get():
        if event.type == pygame.QUIT: pygame.quit(); sys.exit()
        if event.type == pygame.KEYDOWN and not winner:
            if event.key == pygame.K_q: player1.destroy_wall(walls)
            if event.key == pygame.K_RSHIFT: player2.destroy_wall(walls)

    if not winner:
        # Player movement now checks for HELD keys every frame
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: player1.start_movement(0, -1, walls)
        elif keys[pygame.K_s]: player1.start_movement(0, 1, walls)
        elif keys[pygame.K_a]: player1.start_movement(-1, 0, walls)
        elif keys[pygame.K_d]: player1.start_movement(1, 0, walls)
        
        if keys[pygame.K_UP]: player2.start_movement(0, -1, walls)
        elif keys[pygame.K_DOWN]: player2.start_movement(0, 1, walls)
        elif keys[pygame.K_LEFT]: player2.start_movement(-1, 0, walls)
        elif keys[pygame.K_RIGHT]: player2.start_movement(1, 0, walls)
        
        player1.update(dt); player2.update(dt)
        
        # Check collisions only when a player is stationary
        if not player1.is_moving:
            if pygame.sprite.spritecollide(player1, treasures, True): player1.score += 1
            if pygame.sprite.spritecollide(player1, return_traps, True): 
                player1.position.x, player1.position.y = player1.start_pos; player1.rect.topleft = player1.start_pos; player1.target_pos = player1.position.copy()
            if pygame.sprite.spritecollide(player1, stop_traps, True): player1.is_stopped = True; player1.stop_time = time.time() + 3
            if pygame.sprite.spritecollide(player1, slow_traps, True): player1.is_slowed = True; player1.slow_time = time.time() + 5
            if pygame.sprite.spritecollide(player1, haste_buttons, True): player1.is_hasted = True; player1.haste_time = time.time() + 5
            pad_p1 = pygame.sprite.spritecollideany(player1, teleport_pads)
            if pad_p1: player1.teleport(pad_p1.destination)
        
        if not player2.is_moving:
            if pygame.sprite.spritecollide(player2, treasures, True): player2.score += 1
            if pygame.sprite.spritecollide(player2, return_traps, True): 
                player2.position.x, player2.position.y = player2.start_pos; player2.rect.topleft = player2.start_pos; player2.target_pos = player2.position.copy()
            if pygame.sprite.spritecollide(player2, stop_traps, True): player2.is_stopped = True; player2.stop_time = time.time() + 3
            if pygame.sprite.spritecollide(player2, slow_traps, True): player2.is_slowed = True; player2.slow_time = time.time() + 5
            if pygame.sprite.spritecollide(player2, haste_buttons, True): player2.is_hasted = True; player2.haste_time = time.time() + 5
            pad_p2 = pygame.sprite.spritecollideany(player2, teleport_pads)
            if pad_p2: player2.teleport(pad_p2.destination)
            
        # Swap logic needs to check both players but trigger once
        if (not player1.is_moving and pygame.sprite.spritecollideany(player1, swap_pads)) or \
           (not player2.is_moving and pygame.sprite.spritecollideany(player2, swap_pads)):
            swap_pads.empty()
            p1_temp, p2_temp = player1.position.copy(), player2.position.copy()
            player1.position, player2.position = p2_temp, p1_temp
            player1.target_pos, player2.target_pos = player1.position.copy(), player2.position.copy()
            # Update rects immediately after swap to prevent visual glitches
            player1.rect.topleft = (round(player1.position.x), round(player1.position.y))
            player2.rect.topleft = (round(player2.position.x), round(player2.position.y))

        if player1.score >= 3: winner = "Player 1 WON!"
        elif player2.score >= 3: winner = "Player 2 WON!"

    # --- Rendering ---
    WINDOW.fill((0, 0, 0))
    for y in range(MAP_HEIGHT_IN_BLOCKS):
        for x in range(MAP_WIDTH_IN_BLOCKS): WINDOW.blit(GROUND_IMG, (x * BLOCK_SIZE, y * BLOCK_SIZE))
    return_traps.draw(WINDOW); stop_traps.draw(WINDOW); slow_traps.draw(WINDOW); haste_buttons.draw(WINDOW)
    swap_pads.draw(WINDOW); teleport_pads.draw(WINDOW); treasures.draw(WINDOW); walls.draw(WINDOW); players.draw(WINDOW)
    
    # Render player status effects
    if player1.is_stopped or player1.is_slowed or player1.is_hasted:
        WINDOW.blit(STATUS_EFFECT_IMG, player1.rect)
    if not player1.can_destroy_wall: 
        WINDOW.blit(COOLDOWN_EFFECT_IMG, player1.rect)
    if player2.is_stopped or player2.is_slowed or player2.is_hasted:
        WINDOW.blit(STATUS_EFFECT_IMG, player2.rect)
    if not player2.can_destroy_wall: 
        WINDOW.blit(COOLDOWN_EFFECT_IMG, player2.rect)
    
    # Render HUD
    hud_text = f"Player 1: {player1.score} / 3   |   Player 2: {player2.score} / 3"
    hud_surface = SCORE_FONT.render(hud_text, True, (255, 255, 255))
    hud_rect = hud_surface.get_rect(centerx=WINDOW_WIDTH / 2, top=10)
    WINDOW.blit(hud_surface, hud_rect)
    
    if winner: 
        display_winner(winner); pygame.quit(); sys.exit()
    
    pygame.display.flip()
