# Fake Port Scanner (Simulation) – by Grant Ruffner

## Overview

This is a **simulated port scanner** written in Python.

It does **not** perform real network scans.  
Instead, it **models how a port scanner works** by reading a list of targets from a file and applying simple rules to decide if each port is:

- `OPEN`
- `FILTERED`
- `CLOSED`

This project is designed to:
- Practice Python programming.
- Show basic understanding of **ports** and **network services**.
- Build a small, security-flavored tool that can be improved over time (GUI, .exe, etc.).

---

## How It Works (Simple English)

1. You create a text file called `targets.txt`.
2. Each line in `targets.txt` has a **host** and a **port**, like this:

   ```text
   192.168.0.10:22
   192.168.0.10:80
   10.0.0.5:3389
   localhost:443
   192.168.0.10:36
   ```

3. The script:
   - Reads each line.
   - Splits it into `host` and `port`.
   - Uses simple **rules** to decide if the port is:
     - `OPEN`
     - `FILTERED`
     - `CLOSED`

4. Results are:
   - Grouped by **host**.
   - Followed by a **summary** of how many ports were open / filtered / closed.

---

## Example Output

With an input like:

```text
192.168.0.10:36
192.168.0.10:22
192.168.0.10:80
10.0.0.5:3389
localhost:443
```

The script can produce:

Host: 192.168.0.10
  Port 36: CLOSED
  Port 22: OPEN
  Port 80: OPEN

Host: 10.0.0.5
  Port 3389: FILTERED

Host: localhost
  Port 443: OPEN

--- Scan Summary ---
Total targets: 5
OPEN: 3
FILTERED: 1
CLOSED: 1

## Fake Scan Rules

These are not real network checks.

They’re simple rules to simulate typical behavior:


- Ports in COMMON_OPEN_PORTS are treated as OPEN:
  - 22 (SSH)
  - 80 (HTTP)
  - 443 (HTTPS)

-Ports in SENSITIVE_PORTS are treated as FILTERED:
  - 3389 (RDP)

- Any other port is treated as CLOSED.

This can be easily changed in the code if needed.

Files
- fake_port_scanner.py
 Main script that:
  - Loads targets from targets.txt
  - Simulates scanning
  - Groups results by host
  - Prints a summary

- targets.txt
 Input file with targets in the format:

  1. host:port

 How to Run (Python)

1. Make sure you have Python 3 installed.

2. Put fake_port_scanner.py and targets.txt in the same folder.

3. Open a terminal / command prompt in that folder.

4. Run: python fake_port_scanner.py

You should see the grouped host output and the summary at the end.

 Future Improvements (Planned)

- Add a GUI window (e.g., using tkinter) so users can:
  - Click a button to run the scan.
  - See results in a text box instead of the console.

- Package the GUI version as a Windows .exe (using PyInstaller) for easy use without installing Python.

- Add:
  - Logging to a file (e.g., scan_log.txt).
  - More detailed rules for ports and services.
  - Command-line options (e.g., custom input file name).

  Security Learning Connection
Even though this is a fake scanner, it shows:

 - What a port is (a numbered endpoint for network services).
 - The idea of ports being:
  - OPEN (service is reachable),
  - FILTERED (blocked or heavily restricted),
  - CLOSED (no service listening).
 - How security tools process targets and produce:
  - Per-host reports.
  - Overall scan summaries.

This project is a step toward more advanced security tools and helps build:

- Python skills
- Systems thinking
- Security mindset
