import pygame
import json
import os

# ---== Configuration ==---
WIDTH, HEIGHT = 1100, 700 
BG_COLOR = (30, 30, 30)
SAVE_FILE = "paint_recipes.json"

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(" ---== Grant's Primary Color Mixing Lab. ==---")

# Fonts
font_sm = pygame.font.SysFont("Arial", 14)
font = pygame.font.SysFont("Arial", 16)
font_bold = pygame.font.SysFont("Arial", 18, bold=True)

# UI Elements
PIGMENTS = {
    "Red": {"color": (220, 20, 60), "pos": (90, 100)},
    "Yellow": {"color": (255, 215, 0), "pos": (90, 190)},
    "Blue": {"color": (0, 71, 171), "pos": (90, 280)},
    "White": {"color": (255, 255, 255), "pos": (90, 370)},
    "Black": {"color": (10, 10, 10), "pos": (90, 460)}
}

# ---== State ==---
parts = {"Red": 0, "Yellow": 0, "Blue": 0, "White": 0, "Black": 0}
palette = []
reset_warning = False
delete_index = -1
pending_recipe = None  
scroll_y = 0  

# ---== Persistence ==---
def save_recipes(data):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)

def load_recipes():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f: return json.load(f)
        except: return []
    return []

palette = load_recipes()

# ---== Fixed Color Math ==---
def ryb_to_rgb(r_p, y_p, b_p):
    total = r_p + y_p + b_p
    if total == 0: return 255.0, 255.0, 255.0
    r, y, b = r_p/total, y_p/total, b_p/total
    R, G, B_out = r + y, y + 0.5 * b, b
    mv = max(R, G, B_out, 1.0)
    return (R/mv * 255), (G/mv * 255), (B_out/mv * 255)

def mix_paint(p):
    total_p = p.get("Red", 0) + p.get("Yellow", 0) + p.get("Blue", 0)
    r, g, b, vol = 255.0, 255.0, 255.0, 0.0
    if total_p > 0:
        r, g, b = ryb_to_rgb(p.get("Red", 0), p.get("Yellow", 0), p.get("Blue", 0))
        vol = float(total_p)
    for n, nc in [("White", 255.0), ("Black", 0.0)]:
        val = p.get(n, 0)
        if val > 0:
            tv = vol + val
            r, g, b = [(c * vol + nc * val) / tv for c in (r, g, b)]
            vol = tv
    return (int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b))))

# ---== UI Components ==---
def draw_legend(surface):
    pygame.draw.rect(surface, (20, 20, 20), (0, HEIGHT - 80, WIDTH, 80))
    pygame.draw.line(surface, (100, 100, 100), (0, HEIGHT - 80), (WIDTH, HEIGHT - 80), 2)
    shift_held = pygame.key.get_mods() & pygame.KMOD_SHIFT
    mode_text = "SUBTRACT MODE" if shift_held else "ADD MODE"
    mode_color = (255, 100, 100) if shift_held else (100, 255, 100)
    items = [f"[R,Y,B,W,K]: {mode_text}", "[S] Save", "[Space] Clear", "[Arrows] Scroll"]
    x, p = 30, 45
    for item in items:
        c = mode_color if "MODE" in item else (180, 180, 180)
        t = font_sm.render(item, True, c)
        surface.blit(t, (x, HEIGHT - 50)); x += t.get_width() + p
    tip = "Shift + Key sub | Click Bowl to Save | R-Click sub Color | Click My Colors to add in"
    surface.blit(font_sm.render(tip, True, (120, 120, 120)), (30, HEIGHT - 25))

def draw_ui(surface, p_parts, p_list, cur_col, scroll_pos):
    mx, my = pygame.mouse.get_pos()
    # Buckets
    for name, data in PIGMENTS.items():
        dist = ((mx - data["pos"][0])**2 + (my - data["pos"][1])**2)**0.5
        is_h = dist < 35
        pygame.draw.circle(surface, data["color"], data["pos"], 35)
        pygame.draw.circle(surface, (255,255,255) if is_h else (150,150,150), data["pos"], 35, 3 if is_h else 2)
        surface.blit(font_bold.render(f"{name}: {p_parts[name]}", True, (255, 255, 255)), (data["pos"][0] + 55, data["pos"][1] - 10))

    # Bowl
    bc = (520, 350)
    pygame.draw.circle(surface, (200, 200, 200), bc, 160)
    pygame.draw.circle(surface, cur_col, bc, 150)
    if (((mx - bc[0])**2 + (my - bc[1])**2)**0.5) < 150 and not pending_recipe and any(v > 0 for v in p_parts.values()):
        pygame.draw.circle(surface, (255, 255, 255), bc, 150, 3)
        st = font_bold.render("CLICK BOWL TO SAVE", True, (255, 255, 255))
        surface.blit(st, (bc[0] - st.get_width()//2, 340))

    # Sidebar
    pygame.draw.rect(surface, (45, 45, 45), (800, 0, 300, HEIGHT - 80))
    up_btn = pygame.Rect(1060, 10, 30, 40)
    dn_btn = pygame.Rect(1060, HEIGHT - 130, 30, 40)
    pygame.draw.rect(surface, (70, 70, 70), up_btn); pygame.draw.rect(surface, (70, 70, 70), dn_btn)
    surface.blit(font_bold.render("^", True, (255, 255, 255)), (1068, 18))
    surface.blit(font_bold.render("v", True, (255, 255, 255)), (1068, HEIGHT - 122))
    
    recipe_area = pygame.Surface((250, HEIGHT - 140), pygame.SRCALPHA)
    for i, rec in enumerate(p_list):
        py = (i * 85) + scroll_pos
        if -100 < py < HEIGHT:
            prev = mix_paint(rec)
            pygame.draw.rect(recipe_area, prev, (10, py, 40, 75))
            pygame.draw.rect(recipe_area, (150, 150, 150), (10, py, 40, 75), 1)
            if delete_index == i:
                recipe_area.blit(font_bold.render("R-CLICK AGAIN", True, (255, 100, 100)), (60, py + 10))
                recipe_area.blit(font_bold.render("TO DELETE", True, (255, 100, 100)), (60, py + 30))
            else:
                recipe_area.blit(font_bold.render(f"Mix #{i+1}:", True, (255, 255, 255)), (60, py))
                dna = ", ".join([f"{k[0]}:{v}" for k, v in rec.items() if v > 0])
                recipe_area.blit(font.render(dna, True, (180, 180, 180)), (60, py + 22))

    surface.blit(recipe_area, (810, 60))
    pygame.draw.rect(surface, (45, 45, 45), (800, 0, 260, 60))
    surface.blit(font_bold.render("My Colors", True, (200, 200, 200)), (820, 20))

    # Popup 
    if pending_recipe:
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); ov.fill((0, 0, 0, 200)); surface.blit(ov, (0, 0))
        bx = pygame.Rect(325, 280, 450, 200); pygame.draw.rect(surface, (60, 60, 60), bx); pygame.draw.rect(surface, (200, 200, 200), bx, 2)
        tit = font_bold.render("MIX OPTIONS", True, (255, 255, 255)); surface.blit(tit, (550 - tit.get_width()//2, 300))
        btns = [(pygame.Rect(350, 360, 120, 50), "REPLACE (1)", (80, 80, 80)), (pygame.Rect(490, 360, 120, 50), "ADD TO (2)", (80, 80, 80)), (pygame.Rect(630, 360, 120, 50), "CANCEL (Esc)", (150, 50, 50))]
        for r, l, c in btns:
            pygame.draw.rect(surface, c, r); pygame.draw.rect(surface, (200, 200, 200), r, 1)
            bt = font_sm.render(l, True, (255, 255, 255)); surface.blit(bt, (r.centerx - bt.get_width()//2, r.centery - bt.get_height()//2))

    draw_legend(surface)

# ---== Main ==---
running = True
while running:
    screen.fill(BG_COLOR)
    current_color = mix_paint(parts)
    for event in pygame.event.get():
        if event.type == pygame.QUIT: save_recipes(palette); running = False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: scroll_y = min(0, scroll_y + 40)
            if event.key == pygame.K_DOWN:
                max_s = max(0, (len(palette) * 85) - (HEIGHT - 200))
                scroll_y = max(-max_s, scroll_y - 40)

        if event.type == pygame.MOUSEWHEEL:
            scroll_y += event.y * 35
            max_s = max(0, (len(palette) * 85) - (HEIGHT - 200))
            scroll_y = max(-max_s, min(0, scroll_y))

        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            if 1060 <= mx <= 1090:
                if 10 <= my <= 50: scroll_y = min(0, scroll_y + 85)
                if HEIGHT-130 <= my <= HEIGHT-90:
                    max_s = max(0, (len(palette) * 85) - (HEIGHT - 200))
                    scroll_y = max(-max_s, scroll_y - 85)

            if pending_recipe:
                if 350 <= mx <= 470 and 360 <= my <= 410: parts = pending_recipe.copy(); pending_recipe = None
                elif 490 <= mx <= 610 and 360 <= my <= 410:
                    for k in PIGMENTS: parts[k] = parts.get(k, 0) + pending_recipe.get(k, 0)
                    for n in ["White", "Black"]: parts[n] = parts.get(n,0) + pending_recipe.get(n,0)
                    pending_recipe = None
                elif 630 <= mx <= 750 and 360 <= my <= 410: pending_recipe = None
                continue

            old_del = delete_index; delete_index = -1; reset_warning = False
            if (((mx - 520)**2 + (my - 350)**2)**0.5) < 150 and event.button == 1:
                if any(v > 0 for v in parts.values()): palette.append(parts.copy()); save_recipes(palette)

            for name, data in PIGMENTS.items():
                if (((mx - data["pos"][0])**2 + (my - data["pos"][1])**2)**0.5) < 35:
                    if event.button == 1: parts[name] += 1
                    elif event.button == 3: parts[name] = max(0, parts[name] - 1)

            if 800 < mx < 1060 and 60 < my < HEIGHT - 80:
                slot = (my - 60 - scroll_y) // 85
                if 0 <= slot < len(palette):
                    if event.button == 3:
                        if old_del == slot: palette.pop(slot); save_recipes(palette)
                        else: delete_index = slot
                    elif event.button == 1:
                        if any(v > 0 for v in parts.values()): pending_recipe = palette[slot].copy()
                        else: parts = palette[slot].copy()

        if event.type == pygame.KEYDOWN:
            if pending_recipe:
                if event.key == pygame.K_1: parts = pending_recipe.copy(); pending_recipe = None
                elif event.key == pygame.K_2:
                    for k in parts: parts[k] = parts.get(k,0) + pending_recipe.get(k, 0)
                    pending_recipe = None
                elif event.key == pygame.K_ESCAPE: pending_recipe = None
                continue
            keys = {pygame.K_r: "Red", pygame.K_y: "Yellow", pygame.K_b: "Blue", pygame.K_w: "White", pygame.K_k: "Black"}
            amt = -1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
            if event.key in keys: parts[keys[event.key]] = max(0, parts[keys[event.key]] + amt)
            if event.key == pygame.K_s and any(v > 0 for v in parts.values()): palette.append(parts.copy()); save_recipes(palette)
            if event.key == pygame.K_SPACE:
                if any(v > 0 for v in parts.values()):
                    if not reset_warning: reset_warning = True
                    else: parts = {k: 0 for k in parts}; reset_warning = False

    draw_ui(screen, parts, palette, current_color, scroll_y)
    if reset_warning:
        msg = font_bold.render("PRESS SPACE AGAIN TO CLEAR", True, (255, 100, 100))
        screen.blit(msg, (520 - msg.get_width()//2, 350))
    pygame.display.flip()
pygame.quit()