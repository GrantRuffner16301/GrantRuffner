
# Retro Pong - JavaScript Edition 🕹️
A high-performance, browser-based implementation of the classic Pong. This project demonstrates real-time rendering, physics-based collision detection, and autonomous AI logic using the HTML5 Canvas API.

## 🚀 Why This is "Beast Mode"
While most basic Pong clones use simple 'if' statements, this version includes:
* **Dynamic AI Scaling:** The right-hand paddle doesn't just "cheat"—it uses a tracking algorithm with a 0.9 speed factor to simulate human-like reaction delay.
* **Elastic Physics:** Implements incremental velocity multipliers. Every time the ball hits a paddle, the speed increases by 10% (`sx *= -1.1`), forcing the player to adapt to an accelerating game state.
* **Multi-Object Collision Logic:** Features a `players` list of extra bouncing objects (purple squares) that utilize independent vector movement and boundary detection logic.
* **Cross-Language Translation:** This is a direct logical port of my Python version, showcasing the ability to translate game loops across different execution environments (Browser vs. Local Interpreter).

## 🛠️ Technical Stack
* **Language:** JavaScript (ES6+)
* **Graphics:** HTML5 Canvas API
* **Logic:** `requestAnimationFrame` for a smooth 60FPS game loop
* **Input Handling:** Event-driven keyboard listeners (W/S keys)

## 🎮 How to Play
1. Open `index.html` in any modern browser.
2. Use the **'W'** and **'S'** keys to move your paddle.
3. Survive as the ball gets faster with every hit!

## 📸 Preview
![Pong Screenshot](assets/pong_preview.png)
