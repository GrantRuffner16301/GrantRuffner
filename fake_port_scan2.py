import tkinter as tk
from tkinter import scrolledtext, filedialog
from collections import defaultdict
import os

COMMON_OPEN_PORTS = {22, 80, 443}
SENSITIVE_PORTS = {3389}

def load_targets(filepath):
    targets = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                host, port_str = line.split(":", 1)
                try:
                    port = int(port_str)
                    targets.append((host, port))
                except ValueError:
                    pass 
        return targets
    except Exception as e:
        return None

def fake_scan_port(host, port):
    if port in COMMON_OPEN_PORTS:
        return "OPEN"
    elif port in SENSITIVE_PORTS:
        return "FILTERED"
    else:
        return "CLOSED"

def select_file_and_scan(display_area):
    # This opens the system file browser
    file_path = filedialog.askopenfilename(
        title="Select Targets File",
        filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
    )
    
    if not file_path:
        return # User cancelled

    display_area.delete('1.0', tk.END)
    display_area.insert(tk.END, f"Scanning: {os.path.basename(file_path)}\n" + ("="*30) + "\n")
    
    targets = load_targets(file_path)
    if targets is None:
        display_area.insert(tk.END, "Error: Could not read file.")
        return

    results_by_host = defaultdict(list)
    open_count = filtered_count = closed_count = 0

    for host, port in targets:
        status = fake_scan_port(host, port)
        results_by_host[host].append((port, status))
        if status == "OPEN": open_count += 1
        elif status == "FILTERED": filtered_count += 1
        elif status == "CLOSED": closed_count += 1

    for host, entries in results_by_host.items():
        display_area.insert(tk.END, f"\nHost: {host}\n")
        for port, status in entries:
            display_area.insert(tk.END, f"  Port {port}: {status}\n")

    display_area.insert(tk.END, "\n--- Scan Summary ---\n")
    display_area.insert(tk.END, f"Total targets: {len(targets)}\n")
    display_area.insert(tk.END, f"OPEN: {open_count} | FILTERED: {filtered_count} | CLOSED: {closed_count}")

# GUI Setup
root = tk.Tk()
root.title("Port Scan Utility")
root.geometry("600x500")

# Instruction Label
label = tk.Label(root, text="Select a .txt file containing 'host:port' on each line", pady=10)
label.pack()

# Browse & Run Button
btn = tk.Button(root, text="Browse File & Run Scan", command=lambda: select_file_and_scan(txt), 
               bg="#2ecc71", fg="white", font=("Arial", 10, "bold"), padx=20)
btn.pack(pady=10)

# Output Display
txt = scrolledtext.ScrolledText(root, width=70, height=25, font=("Consolas", 10))
txt.pack(padx=15, pady=15)

root.mainloop()