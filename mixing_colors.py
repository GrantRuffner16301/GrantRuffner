import pygame

# --- Configuration ---
WIDTH, HEIGHT = 900, 650
BG_COLOR = (35, 35, 35)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Paint Mixing Guide")
font = pygame.font.SysFont("Arial", 20)
font_large = pygame.font.SysFont("Arial", 32, bold=True)

# Define our Pigments
PIGMENTS = {
    "Red": (220, 20, 60),
    "Yellow": (255, 215, 0),
    "Blue": (0, 71, 171),
    "White": (255, 255, 255),
    "Black": (10, 10, 10)
}

# Current Parts (0 = None in the bowl)
parts = {"Red": 0, "Yellow": 0, "Blue": 0, "White": 0, "Black": 0}

def ryb_to_rgb(r_p, y_p, b_p):
    """ Converts RYB parts to an RGB screen color. """
    total = r_p + y_p + b_p
    if total == 0: return (255, 255, 255) # Starting canvas color
    
    # Normalize ratios
    r, y, b = r_p/total, y_p/total, b_p/total

    # Art-style interpolation (Blue + Yellow = Green)
    R = r + y 
    G = y + 0.5 * b
    B = b
    
    # Normalize to keep brightness consistent
    max_val = max(R, G, B, 1.0)
    return (int(R/max_val * 255), int(G/max_val * 255), int(B/max_val * 255))

def mix_paint(p):
    total_pigment = p["Red"] + p["Yellow"] + p["Blue"]
    total_all = total_pigment + p["White"] + p["Black"]
    
    if total_all == 0: return (50, 50, 50) # Empty bowl

    # 1. Start with the RYB base
    if total_pigment > 0:
        base_r, base_g, base_b = ryb_to_rgb(p["Red"], p["Yellow"], p["Blue"])
    else:
        # If only mixing neutrals (White/Black)
        base_r, base_g, base_b = (255, 255, 255) if p["White"] >= p["Black"] else (20, 20, 20)

    # 2. Apply White (Tinting) - Pulls color toward 255
    white_ratio = p["White"] / total_all
    r = base_r + (255 - base_r) * white_ratio
    g = base_g + (255 - base_g) * white_ratio
    b = base_b + (255 - base_b) * white_ratio

    # 3. Apply Black (Shading) - Pulls color toward 0
    black_ratio = p["Black"] / total_all
    r *= (1 - black_ratio)
    g *= (1 - black_ratio)
    b *= (1 - black_ratio)

    return (int(r), int(g), int(b))

def draw_bucket(surface, label, x, y, color, count):
    # Bucket circle
    pygame.draw.circle(surface, color, (x, y), 35)
    pygame.draw.circle(surface, (150, 150, 150), (x, y), 35, 2)
    # Text
    txt = font.render(f"{label}: {count}", True, (255, 255, 255))
    surface.blit(txt, (x - txt.get_width()//2, y + 45))

# --- Main Loop ---
running = True
while running:
    screen.fill(BG_COLOR)
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            # Shift = Subtract, Normal = Add
            amt = -1 if (pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1
            
            if event.key == pygame.K_r: parts["Red"] = max(0, parts["Red"] + amt)
            if event.key == pygame.K_y: parts["Yellow"] = max(0, parts["Yellow"] + amt)
            if event.key == pygame.K_b: parts["Blue"] = max(0, parts["Blue"] + amt)
            if event.key == pygame.K_w: parts["White"] = max(0, parts["White"] + amt)
            if event.key == pygame.K_k: parts["Black"] = max(0, parts["Black"] + amt) # K for Black
            if event.key == pygame.K_SPACE: parts = {k: 0 for k in parts}

    # Draw UI
    draw_bucket(screen, "Red (R)", 100, 100, PIGMENTS["Red"], parts["Red"])
    draw_bucket(screen, "Yellow (Y)", 100, 200, PIGMENTS["Yellow"], parts["Yellow"])
    draw_bucket(screen, "Blue (B)", 100, 300, PIGMENTS["Blue"], parts["Blue"])
    draw_bucket(screen, "White (W)", 100, 400, PIGMENTS["White"], parts["White"])
    draw_bucket(screen, "Black (K)", 100, 500, PIGMENTS["Black"], parts["Black"])

    # Calculate Mix
    current_color = mix_paint(parts)
    
    # Draw "Bowl"
    pygame.draw.circle(screen, (60, 60, 60), (500, 300), 165) # Shadow
    pygame.draw.circle(screen, (200, 200, 200), (500, 300), 160) # Rim
    pygame.draw.circle(screen, current_color, (500, 300), 150) # Paint

    # Info
    msg = "Resulting Shade" if parts["Black"] > 0 else "Resulting Color"
    draw_text = font_large.render(msg, True, (255, 255, 255))
    screen.blit(draw_text, (400, 80))
    
    ctrls = font.render("Keys: R, Y, B, W, K to add | Shift+Key to remove | Space to Reset", True, (150, 150, 150))
    screen.blit(ctrls, (300, 600))

    pygame.display.flip()

pygame.quit()