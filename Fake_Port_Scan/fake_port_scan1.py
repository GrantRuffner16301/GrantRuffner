import tkinter as tk
from tkinter import scrolledtext
from collections import defaultdict

TARGETS_FILE = "targets.txt"
COMMON_OPEN_PORTS = {22, 80, 443}
SENSITIVE_PORTS = {3389}

def load_targets(filename):
    targets = []
    try:
        with open(filename, "r") as f:
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
    except FileNotFoundError:
        return None

def fake_scan_port(host, port):
    if port in COMMON_OPEN_PORTS:
        return "OPEN"
    elif port in SENSITIVE_PORTS:
        return "FILTERED"
    else:
        return "CLOSED"

def run_scan(display_area):
    display_area.delete('1.0', tk.END) # Clear previous results
    targets = load_targets(TARGETS_FILE)
    
    if targets is None:
        display_area.insert(tk.END, f"Error: {TARGETS_FILE} not found!")
        return

    results_by_host = defaultdict(list)
    open_count = filtered_count = closed_count = 0

    for host, port in targets:
        status = fake_scan_port(host, port)
        results_by_host[host].append((port, status))
        if status == "OPEN": open_count += 1
        elif status == "FILTERED": filtered_count += 1
        elif status == "CLOSED": closed_count += 1

    # Output to the GUI window
    for host, entries in results_by_host.items():
        display_area.insert(tk.END, f"\nHost: {host}\n")
        for port, status in entries:
            display_area.insert(tk.END, f"  Port {port}: {status}\n")

    display_area.insert(tk.END, "\n--- Scan Summary ---\n")
    display_area.insert(tk.END, f"Total targets: {len(targets)}\n")
    display_area.insert(tk.END, f"OPEN: {open_count} | FILTERED: {filtered_count} | CLOSED: {closed_count}")

# GUI Setup
root = tk.Tk()
root.title("Port Scan Results")
root.geometry("500x400")

btn = tk.Button(root, text="Run Scan", command=lambda: run_scan(txt))
btn.pack(pady=10)

txt = scrolledtext.ScrolledText(root, width=60, height=20)
txt.pack(padx=10, pady=10)

root.mainloop()
