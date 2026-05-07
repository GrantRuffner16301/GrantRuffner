import tkinter as tk
from tkinter import scrolledtext
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

# Settings
MAX_WORKERS = 30 

def check_port(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.8)
            result = s.connect_ex((host, port))
            return port, "OPEN" if result == 0 else None
    except:
        return port, None

def run_scan(host, start_p, end_p, display_area, status_label, scan_button):
    # Change button to RED and disable it so they don't click it twice
    scan_button.config(text="SCANNING...", bg="#e74c3c", state=tk.DISABLED)
    status_label.config(text="Status: 🛠 Scanning...", fg="#e67e22")
    
    display_area.insert(tk.END, f"🔎 Scanning {host} ({start_p}-{end_p})...\n")
    display_area.see(tk.END)

    found_open = 0
    ports = range(start_p, end_p + 1)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_port, host, port) for port in ports]
        
        for future in futures:
            port, status = future.result()
            if status == "OPEN":
                display_area.insert(tk.END, f"  [+] Port {port}: OPEN\n", "open")
                display_area.see(tk.END)
                found_open += 1

    display_area.insert(tk.END, f"✅ Finished. Found {found_open} open ports.\n\n")
    
    # Reset button back to GREEN and re-enable it
    scan_button.config(text="START SCAN", bg="#2ecc71", state=tk.NORMAL)
    status_label.config(text="Status: Idle", fg="black")

def validate_and_start():
    host = ent_host.get()
    try:
        start_p = int(ent_start.get())
        end_p = int(ent_end.get())
        # Pass the scan_button into the function so it can be modified
        threading.Thread(target=run_scan, args=(host, start_p, end_p, txt, lbl_status, btn_scan), daemon=True).start()
    except ValueError:
        txt.insert(tk.END, "⚠️ Error: Ports must be numbers!\n")

def clear_output():
    txt.delete('1.0', tk.END)

# --- GUI Setup ---
root = tk.Tk()
root.title("Python Port Scanner")
root.geometry("450x600")

# Input Section
input_frame = tk.Frame(root, pady=10)
input_frame.pack()

tk.Label(input_frame, text="Target IP/Host:").grid(row=0, column=0, sticky="e")
ent_host = tk.Entry(input_frame)
ent_host.insert(0, "127.0.0.1")
ent_host.grid(row=0, column=1, padx=5, pady=2)

tk.Label(input_frame, text="Start Port:").grid(row=1, column=0, sticky="e")
ent_start = tk.Entry(input_frame, width=10)
ent_start.insert(0, "1")
ent_start.grid(row=1, column=1, sticky="w", padx=5, pady=2)

tk.Label(input_frame, text="End Port:").grid(row=2, column=0, sticky="e")
ent_end = tk.Entry(input_frame, width=10)
ent_end.insert(0, "1024")
ent_end.grid(row=2, column=1, sticky="w", padx=5, pady=2)

# Button Row
btn_frame = tk.Frame(root)
btn_frame.pack(pady=5)

# Define btn_scan globally so validate_and_start can access it
btn_scan = tk.Button(btn_frame, text="START SCAN", command=validate_and_start, 
                     bg="#2ecc71", fg="white", font=("Arial", 10, "bold"), width=15)
btn_scan.grid(row=0, column=0, padx=5)

btn_clear = tk.Button(btn_frame, text="CLEAR", command=clear_output, 
                      bg="#95a5a6", fg="white", font=("Arial", 10, "bold"), width=15)
btn_clear.grid(row=0, column=1, padx=5)

# Status Label
lbl_status = tk.Label(root, text="Status: Idle", font=("Arial", 9, "italic"))
lbl_status.pack()

# Output Section
txt = scrolledtext.ScrolledText(root, width=50, height=22, font=("Consolas", 10))
txt.tag_config("open", foreground="green", font=("Consolas", 10, "bold"))
txt.pack(padx=10, pady=10)

root.mainloop()
