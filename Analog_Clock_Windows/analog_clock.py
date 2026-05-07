# Analog Clock 
# BY: Grant Ruffner

import tkinter as tk
from math import sin, cos, pi
from datetime import datetime
 # Create a function to keep out clock together
def update_clock():
    now = datetime.now()
    hours, minutes, seconds = now.hour % 12, now.minute, now.second

    # Calculate angles so hands have depthor smothness so to say.
    seconds_angle = 90 - (seconds * 6)
    minutes_angle = 90 - (minutes * 6 + seconds * 0.1)
    hours_angle = 90 - (hours * 30 + minutes * 0.5)
    canvas.delete("all")

    # Draw a main clock face and fill
    canvas.create_oval(10, 10, 290, 290, fill="#2c3e50", outline="#3498db", width=4)

    # Can not have a clock without numbers well you could but you know
    for i in range(1, 13):
        angle = 90 - i * 30
        x = 150 + 110 * cos(angle * (pi / 180))
        y = 150 - 110 * sin(angle * (pi / 180))
        canvas.create_text(x, y, text=str(i), fill="white", font=("Helvetica", 14, "bold"))

    # Ok now we can add some arms and fingers
    draw_hand(150, 150, hours_angle, 60, 6, "#ecf0f1")    # Hour
    draw_hand(150, 150, minutes_angle, 90, 4, "#bdc3c7")  # Minute
    draw_hand(150, 150, seconds_angle, 110, 2, "#e74c3c") # Second

    # Lets do like all good time pieces and brand it just above the center pin
    canvas.create_text(150, 130, text="Grant Ruffner", fill="#bdc3c7", font=("Helvetica", 10, "italic", "bold"))
    # Middle pin of the time piece
    canvas.create_oval(144, 144, 156, 156, fill="#e74c3c", outline="#c0392b") 

    # Keep calling our function to keep it running
    root.after(1000, update_clock)

   # Our Function t create the hands and fingers to see where they point
def draw_hand(x, y, angle, length, width, color):
    radian_angle = angle * (pi / 180)
    end_x = x + length * cos(radian_angle)
    end_y = y - length * sin(radian_angle)
    canvas.create_line(x, y, end_x, end_y, width=width, fill=color, capstyle="round")

# Here is where we get into the look of he clock we can make is stylesh here.
root = tk.Tk()
root.title("Floating Clock")
root.overrideredirect(True) 
# We set a color to be transparent 
root.config(bg='black')
root.attributes("-transparentcolor", "black")

# Starting Point at Center of window at about 300 by 300 but we'll make it movable
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = (screen_width // 2) - 150
y = (screen_height // 2) - 150
root.geometry(f'300x300+{x}+{y}')

canvas = tk.Canvas(root, width=300, height=300, bg='black', highlightthickness=0)
canvas.pack()

# Forgot this the first run. I was like dumb ass
# Since there is no title bar, let's add a way to close it
# Right click to get a exit
menu = tk.Menu(root, tearoff=0)
menu.add_command(label="Exit", command=root.destroy)

def do_popup(event):
    try:
        # Put the menu where the right click was at
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

# Make right click show the menu
canvas.bind("<Button-3>", do_popup)

# We want to see our time over other apps while working
root.attributes("-topmost", True)

# Allow dragging the clock since the title bar is gone
def start_move(event):
    root.x = event.x
    root.y = event.y

def stop_move(event):
    root.x = None
    root.y = None

def on_move(event):
    deltax = event.x - root.x
    deltay = event.y - root.y
    x = root.winfo_x() + deltax
    y = root.winfo_y() + deltay
    root.geometry(f"+{x}+{y}")

canvas.bind("<ButtonPress-1>", start_move)
canvas.bind("<B1-Motion>", on_move)

update_clock()
root.mainloop()

# Never stop learning, knowledge is for everyone willing to use seek it out.
