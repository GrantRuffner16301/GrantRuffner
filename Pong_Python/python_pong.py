import pygame
pygame.init()

screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()
running = True

paddle_w = 20
paddle_h = 120
paddle_speed = 6

left_paddle = pygame.Rect(50, 300 - paddle_h//2, paddle_w, paddle_h)
right_paddle = pygame.Rect(750 - paddle_w, 300 - paddle_h//2, paddle_w, paddle_h)

ball_size = 20
ball = pygame.Rect(400 - ball_size//2, 300 - ball_size//2, ball_size, ball_size)
ball_speed_x = 4
ball_speed_y = 4

score_left = 0
score_right = 0
font = pygame.font.SysFont(None, 48)

players = [
    {"x": 100, "y": 100, "w": 25, "h": 25, "sx": 2, "sy": 1},
    {"x": 200, "y": 200, "w": 40, "h": 40, "sx": -1, "sy": 2},
    {"x": 500, "y": 300, "w": 30, "h": 30, "sx": 1.5, "sy": -2},
]

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()

    if keys[pygame.K_w]:
        left_paddle.y -= paddle_speed
    if keys[pygame.K_s]:
        left_paddle.y += paddle_speed

    left_paddle.y = max(0, min(left_paddle.y, 600 - paddle_h))

    if ball.centery > right_paddle.centery:
        right_paddle.y += paddle_speed * 0.9
    else:
        right_paddle.y -= paddle_speed * 0.9

    right_paddle.y = max(0, min(right_paddle.y, 600 - paddle_h))

    ball.x += ball_speed_x
    ball.y += ball_speed_y

    if ball.y <= 0 or ball.y >= 600 - ball_size:
        ball_speed_y *= -1

    if ball.colliderect(left_paddle) or ball.colliderect(right_paddle):
        ball_speed_x *= -1.1  
    
    if ball.x < 0:
        score_right += 1
        ball.x, ball.y = 400, 300
        ball_speed_x = -4
        ball_speed_y = 4

    if ball.x > 800:
        score_left += 1
        ball.x, ball.y = 400, 300
        ball_speed_x = 4
        ball_speed_y = -4

    for p in players:
        p["x"] += p["sx"]
        p["y"] += p["sy"]
        if p["x"] <= 0 or p["x"] >= 800 - p["w"]:
            p["sx"] *= -1
        if p["y"] <= 0 or p["y"] >= 600 - p["h"]:
            p["sy"] *= -1
    '''
    player_x += player_speed
    if player_x<= 0 or player_x >= 800 - player_width:
        player_speed *= -1
    
    player_y += player_speed
    if player_y<=0 or player_y >= 600 - player_height:
        player_speed *= -1

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        player_x -= 1
    if keys[pygame.K_RIGHT]:
        player_x += 1
    if keys[pygame.K_UP]:
        player_y -= 1
    if keys[pygame.K_DOWN]:
        player_y += 1

    player_x = max(0, min(player_x, 800 - player_width))
    player_y = max(0, min(player_y, 600 - player_height))
    '''
    screen.fill((130, 206, 235))
    pygame.draw.rect(screen, (100, 100, 100), (0, 300, 800, 300))
    pygame.draw.rect(screen, (34, 139, 34), (0, 500, 800, 200))
    pygame.draw.circle(screen, (255, 255, 0), (400, 300), 50)
    pygame.draw.ellipse(screen, (200, 0, 200), (300, 400, 200, 80))
    pygame.draw.polygon(screen, (0, 255, 128), [(100, 100), (150, 50), (200, 100)])

    pygame.draw.rect(screen, (255, 255, 255), left_paddle)
    pygame.draw.rect(screen, (255, 255, 255), right_paddle)

    pygame.draw.rect(screen, (255, 255, 255), ball)

    for p in players:
        pygame.draw.rect(screen, (120, 0, 120), (p["x"], p["y"], p["w"], p["h"]))

    score_text = font.render(f"{score_left}   {score_right}", True, (255, 255, 255))
    screen.blit(score_text, (350, 20))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()