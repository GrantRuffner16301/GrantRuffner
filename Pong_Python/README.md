
# Retro Pong - Python Edition 🐍
A robust, desktop-based implementation of Pong built using the Pygame library. This version focuses on object-oriented logic, collision physics, and custom environment rendering.

## 🚀 Why This is "Beast Mode"
This isn't just a copy-paste project; it features advanced logic gates and rendering techniques:
* **The "Conscience" AI:** The right paddle uses a tracking algorithm with a speed dampener (`paddle_speed * 0.9`). This ensures the AI is challenging but "humanly" beatable by introducing a slight tracking lag.
* **Momentum Physics:** Implements a velocity multiplier on paddle contact (`ball_speed_x *= -1.1`). The game literally forces you to get better as the round progresses.
* **Environmental Geometry:** Beyond the game, the code renders a custom "Game Field" using `pygame.draw` (sun, grass, and background layers) to create a unique aesthetic experience.
* **Object Management:** Includes a list-based system for autonomous "rogue" objects that bounce independently, demonstrating clean handling of multiple moving parts in a 2D space.

## 🛠️ Technical Stack
* **Language:** Python 3.12
* **Library:** Pygame
* **Logic:** Rect-based collision detection and delta-time management
* **Rendering:** Layered primitive drawing (rects, circles, ellipses, and polygons)

## 🎮 How to Play
1. Ensure you have Pygame installed: `pip install pygame`
2. Run the script: `python python_pong.py`
3. Control the left paddle with **'W'** and **'S'**.

## 📸 Preview
![Python Pong Screenshot](assets/python_pong_preview.png)
