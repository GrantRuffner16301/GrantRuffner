import tkinter as tk
from tkinter import messagebox
import random

# Game state
board = [""] * 9
current_player = "X"
game_over = False

def check_winner_simple(b):
    win_conditions = [[0,1,2], [3,4,5], [6,7,8], [0,3,6], [1,4,7], [2,5,8], [0,4,8], [2,4,6]]
    for c in win_conditions:
        if b[c[0]] == b[c[1]] == b[c[2]] != "":
            return b[c[0]]
    if "" not in b: return "Draw"
    return None

# --- AI LOGIC ---

def minimax(temp_board, depth, is_maximizing):
    res = check_winner_simple(temp_board)
    if res == "O": return 1
    if res == "X": return -1
    if res == "Draw": return 0

    if is_maximizing:
        best_score = -float('inf')
        for i in range(9):
            if temp_board[i] == "":
                temp_board[i] = "O"
                score = minimax(temp_board, depth + 1, False)
                temp_board[i] = ""
                best_score = max(score, best_score)
        return best_score
    else:
        best_score = float('inf')
        for i in range(9):
            if temp_board[i] == "":
                temp_board[i] = "X"
                score = minimax(temp_board, depth + 1, True)
                temp_board[i] = ""
                best_score = min(score, best_score)
        return best_score

def get_best_move():
    best_score = -float('inf')
    move = None
    for i in range(9):
        if board[i] == "":
            board[i] = "O"
            score = minimax(board, 0, False)
            board[i] = ""
            if score > best_score:
                best_score = score
                move = i
    return move

def computer_move():
    if game_over: return
    difficulty = diff_var.get()
    empty_spots = [i for i, s in enumerate(board) if s == ""]
    
    move = None

    if difficulty == "Easy":
        move = random.choice(empty_spots)
    
    elif difficulty == "Medium":
        # Block user if they are about to win, otherwise random
        for i in empty_spots:
            board[i] = "X"
            if check_winner_simple(board) == "X": move = i; board[i] = ""; break
            board[i] = ""
        if move is None: move = random.choice(empty_spots)

    elif difficulty == "Hard":
        # Try to win first, then block, then random
        for i in empty_spots:
            board[i] = "O"; 
            if check_winner_simple(board) == "O": move = i; board[i] = ""; break
            board[i] = ""
        if move is None:
            for i in empty_spots:
                board[i] = "X"
                if check_winner_simple(board) == "X": move = i; board[i] = ""; break
                board[i] = ""
        if move is None: move = random.choice(empty_spots)

    elif difficulty == "Extremely Hard":
        move = get_best_move()

    if move is not None:
        button_click(move)

# --- UI LOGIC ---

def button_click(index):
    global current_player, game_over
    if game_over or board[index] != "": return
    
    board[index] = current_player
    color = "#3498db" if current_player == "X" else "#e74c3c"
    buttons[index].config(text=current_player, fg=color)
    
    res = check_winner_simple(board)
    if res:
        game_over = True
        messagebox.showinfo("Game Over", "Draw!" if res == "Draw" else f"Player {res} wins!")
    else:
        current_player = "O" if current_player == "X" else "X"
        if current_player == "O" and not game_over:
            root.after(400, computer_move)

def reset_game():
    global board, current_player, game_over
    board = [""] * 9
    current_player = "X"
    game_over = False
    for b in buttons: b.config(text="", bg="SystemButtonFace", fg="black")

root = tk.Tk()
root.title("Tic Tac Toe - Difficulty Modes")

# Difficulty Selector
diff_var = tk.StringVar(value="Medium")
tk.Label(root, text="Difficulty:").grid(row=4, column=0)
tk.OptionMenu(root, diff_var, "Easy", "Medium", "Hard", "Extremely Hard").grid(row=4, column=1, columnspan=2)

buttons = []
for i in range(9):
    btn = tk.Button(root, text="", font=("Arial", 20, "bold"), width=5, height=2, command=lambda i=i: button_click(i))
    btn.grid(row=i//3, column=i%3, padx=5, pady=5)
    buttons.append(btn)

tk.Button(root, text="Restart", command=reset_game, bg="#95a5a6", fg="white").grid(row=3, column=0, columnspan=3, sticky="nsew", pady=5)
root.mainloop()