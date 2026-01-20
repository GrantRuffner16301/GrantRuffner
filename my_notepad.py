# My NotePad 
# By: Grant Ruffner 
# Email: ruffnergrant@gmail.com

# This is a work in progress stuff I learned from self studying python 
# Im still improving it got more ideas for it like adding text to speach and a menu to 
# set transperance so i can see through the app to take notes and stuff with that have to add always on top
# so it stays up front when clicking on other apps 
# Going to use tkinter with python for displayig and user interface for this app
# Now going to collage at maestro University to learn more and maybe this will all change who knows
# To be continued............

import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import simpledialog
from tkinter import font as tkfont
import os

# These are some Globals

# Define the default font properties
default_font_family = "Arial"
default_font_size = 12
# Create a Tkinter font object that will manage the appearance of the text widget
current_font = None # tkfont.Font(family=default_font_family, size=default_font_size) <-- this was causing
# a error because the main window was not created yet opps got ahead of myself

# List to hold file paths for all currently open windows
# This is a vital for multi window stablazation ok i dont know how to spell it sue me
window_file_paths = {} 


# Here is are the Core Functions we made
def get_current_window_info(text_widget):
    # Way to get the root window and current file path from a text widget
    window = text_widget.winfo_toplevel()
    filepath = window_file_paths.get(window)
    return window, filepath

def set_current_file_path(window, filepath):
    # a way to update the file path for a active window
    window_file_paths[window] = filepath
    if filepath:
        window.title(f"Notepad - {filepath}")
    else:
        window.title("Notepad - New File")

def new_file(event=None): # Create function to Create haha but a new file not a function
    # Clears the current text area and resets the file path for the active window
    # Find the text widget that started the command or that has the focus
    text_widget = event.widget if event else tk.focus_get() 
    
    if text_widget and isinstance(text_widget, tk.Text):
        window, _ = get_current_window_info(text_widget)
        text_widget.delete("1.0", "end")
        set_current_file_path(window, None) # Reset the file path for this window

def open_file(event=None): # Created so we can open our files where ever we put them
    text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return
        
    window, _ = get_current_window_info(text_widget)
    
    filepath = filedialog.askopenfilename(
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if not filepath:
        return
    
    text_widget.delete("1.0", "end")
    with open(filepath, "r", encoding="utf-8") as f:
        text_widget.insert("1.0", f.read())
    
    set_current_file_path(window, filepath)

def save_file(event=None): # Create a function to save the file to loaded file location
    text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return
    
    window, current_file = get_current_window_info(text_widget)

    if current_file:
        with open(current_file, "w", encoding="utf-8") as f:
            f.write(text_widget.get("1.0", "end-1c"))
        window.title(f"Notepad - {current_file} (Saved)")
    else:
        save_as_file(text_widget=text_widget) # Save to existing file of go to save as

def save_as_file(event=None, text_widget=None): # Create a function to save it as .txt
    if text_widget is None:
        text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return

    window, _ = get_current_window_info(text_widget)

    filepath = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if not filepath:
        return
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text_widget.get("1.0", "end-1c"))
    
    set_current_file_path(window, filepath)

def print_file(event=None): # Well lets create a function so we can print our work
    # Well use this to send it to the default printer
    text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return
    
    _, current_file = get_current_window_info(text_widget)

    if current_file:
        try:
            os.startfile(current_file, "print")
        except Exception as e:
            messagebox.showerror("Error", f"Cant Print This: {e}")
    else:
        messagebox.showwarning("Print", "You'll need to save this before Printing.")

# Lets set up a way to change our format of text
def toggle_underline(event=None): # lets add underline for taking notes add  or remove from selected words
    text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return
    tag_name = "underline_tag" 

    try:
        if text_widget.tag_ranges("sel"):
            start = text_widget.index("sel.first")
            end = text_widget.index("sel.last")
            
            if tag_name in text_widget.tag_names(start):
                text_widget.tag_remove(tag_name, start, end)
            else:
                text_widget.tag_add(tag_name, start, end)
    except tk.TclError:
        pass

def change_font_size(text_widget): # who doesn't want to change font size
    global current_font
    # We need to open a small dialog window to select the font size
    new_size = simpledialog.askinteger(
        "Font Size", 
        "Enter new font size:", 
        initialvalue=current_font.cget("size"),
        minvalue=6, maxvalue=72
    )
     # If there is changes to font the set them now
    if new_size:
        current_font.configure(size=new_size)
        text_widget.config(font=current_font)

def change_font_family(text_widget, family_name): # Need to be able to change the type of font
    global current_font
    current_font.configure(family=family_name)
    text_widget.config(font=current_font)


def show_about(): # Here we add an about to give a few details about our app
    messagebox.showinfo( # Creates a informational window 
        "About My Notepad","Created by: Grant Ruffner Date: 12/10/2025 \n\nMy Notepad\n\nThis a simple multi-window text editor NotePad app.\n\nCoding Language Used: Python with Tkinter.Code Editor used: Sublime"
    )

def open_character_map(root_window, text_widget): # Here is a little extra characters still playing with
    # We want to create a toplevel window for this  
    char_window = tk.Toplevel(root_window) 
    char_window.title("Character Map")
    char_window.transient(root_window) 

    special_chars = [ # Will add more later
        ('€', 1), ('£', 1), ('¥', 1), ('©', 1), ('®', 1),
        ('™', 1), ('§', 1), ('¶', 1), ('÷', 1), ('×', 1),
        ('±', 1), ('°', 1), ('•', 1), ('✔', 1), ('★', 1)
    ]

    def insert_char(char): # Need a callback function to insert the clicked character
        text_widget.insert(tk.INSERT, char) 
        # Removed char_window.destroy() started with this but then commented it out
        # to allow inserting multiple characters rather the closing the window once something was clicked

    row_num = 0
    col_num = 0
    for char, _ in special_chars:
        btn = tk.Button(char_window, 
                        text=char, 
                        width=3, 
                        font=('Arial', 12), 
                        command=lambda c=char: insert_char(c))
        btn.grid(row=row_num, column=col_num, padx=5, pady=5)
        col_num += 1
        if col_num > 4:
            col_num = 0
            row_num += 1

# These next few parts are the edit operations for undo, redo, select all and you know basic features

def undo(event=None): #  The undo
    text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return
    try:
        text_widget.edit_undo()
    except: pass

def redo(event=None): # The Redo
    text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return
    try:
        text_widget.edit_redo()
    except: pass

def select_all(event=None): # Select all
    text_widget = event.widget if event else tk.focus_get()
    if not (text_widget and isinstance(text_widget, tk.Text)): return
    text_widget.tag_add("sel", "1.0", "end")
    return "break"

# Need to display a window for the app now don't we
def setup_notepad_window(root_window=None, is_main=False):
    # Lets do some configuring here
    global current_font # I removed from the rest at top and placed here to be on the safe side
    if is_main: # Sets up the main Tk() root window
        window = tk.Tk()
        window.title("Notepad") # Give it a title at the top got to name it something
    else: # Sets up a secondary toplevel window
        window = tk.Toplevel(root_window) 
        window.title("Notepad - New Window")

    window.geometry("800x600") # set a default starting size
    # Was getting Error that window didn't exist, so now that a root window exists, it is safe to create the font
    if current_font is None:
        current_font = tkfont.Font(family=default_font_family, size=default_font_size)

    # We also need a place to type in dont we lets add and cofigure it now
    new_text = tk.Text(window, wrap="word", undo=True, font=current_font)
    new_text.pack(fill="both", expand=True)
    new_text.tag_configure("underline_tag", underline=True)
    
    # We set the file path to none and let you select where so go 
    set_current_file_path(window, None) 

    # Lets add a few menus at the to like most apps have you know standard this that stuff
    menubar = tk.Menu(window)

    # This ones Files got to have think its in window its self but add short cut keys just in case 
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="New", accelerator="Ctrl+N", command=new_file)
    file_menu.add_command(label="Open New Window", command=lambda: setup_notepad_window(window)) 
    file_menu.add_command(label="Open", accelerator="Ctrl+O", command=open_file)
    file_menu.add_command(label="Save", accelerator="Ctrl+S", command=save_file)
    file_menu.add_command(label="Save As", command=save_as_file)
    file_menu.add_separator()
    file_menu.add_command(label="Print", accelerator="Ctrl+P", command=print_file)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=window.destroy) # Use .destroy() to close a window for a exit ill have it check for changes later 
    # right now it will just close it and lose all within.
    menubar.add_cascade(label="File", menu=file_menu) # Make the menu drop down

    # The edit menu
    edit_menu = tk.Menu(menubar, tearoff=0)
    edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=undo)
    edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=redo)
    edit_menu.add_separator()
    edit_menu.add_command(label="Underline", accelerator="Ctrl+U", command=toggle_underline)
    edit_menu.add_separator()
    edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=lambda t=new_text: t.event_generate("<<Cut>>")) 
    edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=lambda t=new_text: t.event_generate("<<Copy>>"))
    edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=lambda t=new_text: t.event_generate("<<Paste>>"))
    edit_menu.add_separator()
    edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=select_all)
    menubar.add_cascade(label="Edit", menu=edit_menu)

    # The format menu
    format_menu = tk.Menu(menubar, tearoff=0)

    # Font Size command
    format_menu.add_command(label="Font Size...", command=lambda t=new_text: change_font_size(t)) 
    
    # Font Family submenu
    font_family_menu = tk.Menu(format_menu, tearoff=0) # Still working on adding more
    for family in ["Arial", "Courier New", "Times New Roman", "Verdana", "Impact"]:
        font_family_menu.add_command(label=family, command=lambda f=family, t=new_text: change_font_family(t, f))
    format_menu.add_cascade(label="Font Family", menu=font_family_menu)
    format_menu.add_separator()
    
    # Character Map command
    format_menu.add_command(label="Character Map...", command=lambda: open_character_map(window, new_text)) 
    menubar.add_cascade(label="Format", menu=format_menu)
    
    # Help Menu
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About", command=show_about)
    menubar.add_cascade(label="Help", menu=help_menu)
    window.config(menu=menubar)
    
    # Keyboard shortcuts 
    # Bind to the text widget itself for most editing commands
    new_text.bind("<Control-n>", new_file)
    new_text.bind("<Control-o>", open_file)
    new_text.bind("<Control-s>", save_file)
    new_text.bind("<Control-p>", print_file)
    new_text.bind("<Control-a>", select_all)
    new_text.bind("<Control-u>", toggle_underline)
    # These next two are usually the text widget handles Z/Y internally but fall back again just in case 
    window.bind("<Control-z>", undo)
    window.bind("<Control-y>", redo)
    return window

# Got to be able to start this thing, Don't want just code and no start call to run it. Lets Do This..
if __name__ == "__main__":
    main_window = setup_notepad_window(is_main=True)
    main_window.mainloop()