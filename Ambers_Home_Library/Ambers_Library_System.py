# Amber's Home Library System By: Grant Ruffner Email: ruffnergrant@gmail.com

import sqlite3, datetime, os, uuid
import customtkinter as ctk
import qrcode, cv2
import time # used to track real world time
from PIL import Image, ImageTk
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# --- DATABASE & ASSETS ---
class LibraryDB:
    def __init__(self, db_name="library.db"):
        self.db_name = db_name
        self._init_db()  

    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = 1")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY, title TEXT, author TEXT, isbn TEXT, is_printed INTEGER DEFAULT 0, created_at TIMESTAMP)")
            conn.execute("CREATE TABLE IF NOT EXISTS members (id TEXT PRIMARY KEY, name TEXT, joined_at TIMESTAMP)")
            conn.execute("CREATE TABLE IF NOT EXISTS loans (id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT, member_id TEXT, checkout_date TIMESTAMP, due_date TIMESTAMP, return_date TIMESTAMP)")
    
class AssetGenerator:
    @staticmethod
    def draw_label_at(c, book_id, title, author, x, y):
        temp_filename = f"temp_{uuid.uuid4().hex}.png"
        
        qr = qrcode.QRCode(box_size=10, border=1)
        qr.add_data(book_id)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(temp_filename)
        
        # Draw on the PDF
        c.drawImage(temp_filename, x + 0.1*inch, y + 0.2*inch, width=1.1*inch, height=1.1*inch)
        
        # Text positioning
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 1.3*inch, y + 0.8*inch, title[:15])
        c.setFont("Helvetica", 8)
        c.drawString(x + 1.3*inch, y + 0.6*inch, f"By: {author[:15]}")
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.rect(x, y, 2.5*inch, 1.5*inch)
        
        # Cleanup unique temp file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    @staticmethod
    def create_member_card(member_id, name, file_path, photo_path=None):
        c = canvas.Canvas(file_path, pagesize=(3.5*inch, 2.0*inch))
        
        # Draw the Child's Photo (if provided)
        if photo_path and os.path.exists(photo_path):
            try:
                # We draw the photo as a square on the left
                c.drawImage(photo_path, 0.2*inch, 0.35*inch, width=1.1*inch, height=1.3*inch, preserveAspectRatio=True)
            except:
                pass # If the image is broken, it just skips it
        
        # Draw the QR Code on the right
        qr = qrcode.make(member_id)
        qr.save("temp_m.png")
        c.drawImage("temp_m.png", 2.1*inch, 0.35*inch, width=1.2*inch, height=1.2*inch)
        
        # Text positioning
        c.setFont("Helvetica-Bold", 14)
        c.drawString(0.2*inch, 1.7*inch, "Library Card")
        
        c.setFont("Helvetica", 12)
        # Move name to the center/bottom if there is a photo
        c.drawCentredString(1.75*inch, 0.15*inch, name)
        
        c.showPage()
        c.save()
        if os.path.exists("temp_m.png"):
            os.remove("temp_m.png")

# --- SCAN STATION (Core Checkout Logic) ---
class ScanStation(ctk.CTkToplevel):
    def __init__(self, master, db):
        # Initialize the popup window
        super().__init__(master)
        self.title("Scan Station")
        self.geometry("600x700")
        
        # Database and Session Tracking
        self.db = db
        self.active_member_id = None
        self.active_member_name = None
        
        # Cooldown and Visual Overlay Variables
        self.last_scan_time = 0         # Tracks time of last successful scan
        self.overlay_text = ""          # Text to show on camera feed
        self.overlay_color = (0, 255, 0) # Color of the text (Green by default)
        self.overlay_expiry = 0         # Time when text should disappear
        
        # UI Elements
        self.label = ctk.CTkLabel(self, text="Please scan a Member Card", 
                                  font=("Arial", 18, "bold"), text_color="#3a7ebf")
        self.label.pack(pady=10)
        
        self.vid_label = ctk.CTkLabel(self, text="")
        self.vid_label.pack()
        
        self.status = ctk.CTkTextbox(self, width=500, height=150, font=("Arial", 13))
        self.status.pack(pady=10)
        
        ctk.CTkButton(self, text="Clear Log / Logout", command=self.reset_session).pack(pady=5)
        
        # Initialize Camera and Detector
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.detector = cv2.QRCodeDetector()
        
        # Start Loop
        self.update_frame()

    def reset_session(self):
        """Logs out current member and clears the screen."""
        self.active_member_id = None
        self.active_member_name = None
        self.label.configure(text="Please scan a Member Card", text_color="#3a7ebf")
        self.status.insert("0.0", "--- Session Reset ---\n")

    def update_frame(self):
        if not self.winfo_exists(): return
        
        ret, frame = self.cap.read()
        if ret:
            # 1. Scanning Logic
            data, bbox, _ = self.detector.detectAndDecode(frame)
            if data and (time.time() - self.last_scan_time > 2.0):
                self.process_scan(data)
                self.last_scan_time = time.time()

            # 2. Draw Overlay
            if time.time() < self.overlay_expiry:
                cv2.putText(frame, self.overlay_text, (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.overlay_color, 3)

            # Convert BGR to RGB
            color_converted = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(color_converted)
            
            # Use CTkImage instead of ImageTk.PhotoImage
            self.tk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(400, 300))
            
            self.vid_label.configure(image=self.tk_img)
            
        self.after(15, self.update_frame)

    def process_scan(self, data):
        """Handles the library logic for checkouts and returns."""
        with self.db._get_connection() as conn:
            
            def show_msg(text, color=(0, 255, 0)):
                """Helper to trigger the on-screen message."""
                self.overlay_text = text
                self.overlay_color = color
                self.overlay_expiry = time.time() + 2.0

            # Check for Member
            m = conn.execute("SELECT * FROM members WHERE id = ?", (data,)).fetchone()
            if m:
                if self.active_member_id != data:
                    self.active_member_id = data
                    self.active_member_name = m['name']
                    self.label.configure(text=f"Active Member: {m['name']}", text_color="green")
                    self.status.insert("0.0", f"Member Logged In: {m['name']}\n")
                    show_msg(f"HELLO {m['name'].upper()}")
                return

            # Check for Book
            b = conn.execute("SELECT * FROM books WHERE id = ?", (data,)).fetchone()
            if b:
                # Check for existing loan (Return Logic)
                loan = conn.execute("SELECT * FROM loans WHERE book_id = ? AND return_date IS NULL", (data,)).fetchone()
                if loan:
                    conn.execute("UPDATE loans SET return_date = ? WHERE book_id = ?", (datetime.datetime.now(), data))
                    self.status.insert("0.0", f"RETURNED: {b['title']}\n")
                    show_msg("RETURN SUCCESS", (255, 255, 0)) # Cyan/Yellow
                    return

                # Checkout Logic
                if not self.active_member_id:
                    self.status.insert("0.0", "⚠️ ERROR: Scan a Member Card first!\n")
                    show_msg("SCAN MEMBER CARD", (0, 0, 255)) # Red
                    return

                # Check "One Book Per Kid" Rule
                active_loan = conn.execute("SELECT * FROM loans WHERE member_id = ? AND return_date IS NULL", (self.active_member_id,)).fetchone()
                if active_loan:
                    self.status.insert("0.0", f"❌ REJECTED: Already has a book!\n")
                    show_msg("LIMIT REACHED", (0, 0, 255)) # Red
                else:
                    due = datetime.datetime.now() + datetime.timedelta(days=7)
                    conn.execute("INSERT INTO loans (book_id, member_id, checkout_date, due_date) VALUES (?, ?, ?, ?)", 
                                 (data, self.active_member_id, datetime.datetime.now(), due))
                    self.status.insert("0.0", f"CHECKOUT: {b['title']} to {self.active_member_name}\n")
                    show_msg("CHECKOUT SUCCESS", (0, 255, 0)) # Green

    def destroy(self):
        # Stop the camera immediately
        if self.cap.isOpened():
            self.cap.release()
        # Close any OpenCV pop-up windows
        cv2.destroyAllWindows()
        # Kill the actual Tkinter window
        super().destroy()

# --- DASHBOARDS ---
class HelpWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master); self.title("Library Guide"); self.geometry("500x500")
        ctk.CTkLabel(self, text="📘 System Guide", font=("Arial", 22, "bold")).pack(pady=15)
        box = ctk.CTkTextbox(self, width=450, height=450, font=("Arial", 13))
        box.pack(padx=20, pady=10)
        guide = """
ADDING MEMBERS 👦
Go to 'Add New Child' then type in their Name and you have the Option to add a 
photo to that card as well. The system generates a PDF 
Library Card in the 'cards' folder here the main apps is stored.

SEARCH CHILD
Here is where you can view a list of every child that has library card through 
this system. You can delete names from here using the id displayed in the window.
to reprint library card you can go to the "cards" folder and select the card you 
need to reprint for there.

ADDING BOOKS 📕
To add a book to the Library Inventory System open the dashboard. 
Type it the Books name and The auther of the book, Then Click Save.
To view the books Go to the Search Inventory. From there to can print
the QR for the books you added, y64 can batch print the QR coded if you
reprint youll have to go to the app folder in labels and delete the batch 
file.

SEARCH INVENTORY 📋
Here you can see the book that have been added to the system. You can delete
wrong entries and discarded book from here. You can batch print QR codes from
here as well you can sellect more than one for paper saving.

OPEN SCAN STATION 
This is where you will scan the child's library card and it will give you
information related to that child. You scan library card the the book that 
the child is taking. It will mark it a checked out or in accordingly

ONE BOOK PER KID RULE 🛑
The scanner enforces a strict limit: one child can only have one book checked 
out at a time. If they try to scan a second, the system will block it 
until they return the first one.

SCANNING FLOW 📸
- Scan CHILD CARD first (turns the top bar Green).
- Scan BOOK LABEL second.
- To RETURN: Just scan the book label (no card needed).

VIEW LIVE LOANS
This is where you an get a over view of all the books that are 
loaned out and to who.

ABOUT
This was a idea that the mother of my children had. So I kind of made her idea
come to be. This is just a demo to show her, if she can think it. somehow
we can build it. If it takes learning new things then I say Lets Do This.
We are working together on a better UI and always improving on what we
Know and learn.

CREATED FOR:
Amber **** ********
Happy BirthDay

BY: Grant Ruffner 
Email: ruffnergrant@gmail.com
        """
        box.insert("0.0", guide); box.configure(state="disabled")

class LibraryApp(ctk.CTk):
    def __init__(self):
        super().__init__(); self.title("Amber's Library System"); self.geometry("350x650")
        self.db, self.asset_gen = LibraryDB(), AssetGenerator()
        
        ctk.CTkLabel(self, text="📚 Amber's Library", font=("Arial", 26, "bold")).pack(pady=40)
        ctk.CTkButton(self, text="📸 Open Scan Station", height=45, fg_color="#2b719e", command=lambda: ScanStation(self, self.db)).pack(pady=10)
        ctk.CTkButton(self, text="🔍 Search Inventory", height=45, command=self.open_inventory).pack(pady=10)
        ctk.CTkButton(self, text="🔍 Search Children", height=45, command=self.open_member_search).pack(pady=10)
        ctk.CTkButton(self, text="➕ Add New Book", height=45, command=self.open_book_entry).pack(pady=10)
        ctk.CTkButton(self, text="👦 Add A Child", height=45, command=self.open_member_entry).pack(pady=10)
        ctk.CTkButton(self, text="📋 View Live Loans", height=45, fg_color="#d97706", command=self.open_live_loans).pack(pady=10)
        ctk.CTkButton(self, text="❓ System Guide", height=45, fg_color="gray", command=lambda: HelpWindow(self)).pack(pady=10)
        

    def open_book_entry(self):
        win = ctk.CTkToplevel(self); win.title("Add Book"); win.geometry("300x350")
        ctk.CTkLabel(win, text="Title:").pack(); t = ctk.CTkEntry(win); t.pack()
        ctk.CTkLabel(win, text="Author:").pack(); a = ctk.CTkEntry(win); a.pack()
        def save():
            if t.get():
                bid = str(uuid.uuid4())
                with self.db._get_connection() as conn: 
                    conn.execute("INSERT INTO books (id, title, author, created_at) VALUES (?, ?, ?, ?)", 
                                 (bid, t.get(), a.get(), str(datetime.datetime.now())))
                    conn.commit() 
                win.destroy()
        ctk.CTkButton(win, text="Save", command=save).pack(pady=20)

    def open_member_entry(self):
        win = ctk.CTkToplevel(self)
        win.title("Add Child")
        win.geometry("400x500")
        
        self.temp_photo_path = None
        
        ctk.CTkLabel(win, text="Name:").pack(pady=5)
        n = ctk.CTkEntry(win)
        n.pack(pady=5)

        # Photo Preview Label
        self.photo_preview = ctk.CTkLabel(win, text="No Photo Captured", width=200, height=150, fg_color="gray20")
        self.photo_preview.pack(pady=10)

        def take_photo_live():
            # A small nested window for the camera
            cam_win = ctk.CTkToplevel(win)
            cam_win.title("Capture Photo")
            
            vid_label = ctk.CTkLabel(cam_win, text="")
            vid_label.pack()
            
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

            def update_cam():
                ret, frame = cap.read()
                if ret:
                    # Mirror the frame for a "Selfie" feel
                    frame = cv2.flip(frame, 1)
                    
                    # Convert to RGB for CTk
                    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(img)
                    tk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(320, 240))
                    vid_label.configure(image=tk_img)
                    vid_label._image = tk_img # Keep reference
                
                if cam_win.winfo_exists():
                    cam_win.after(15, update_cam)
                else:
                    cap.release()

            def capture():
                ret, frame = cap.read()
                if ret:
                    frame = cv2.flip(frame, 1)
                    os.makedirs("temp_assets", exist_ok=True)
                    path = f"temp_assets/{uuid.uuid4()}.jpg"
                    cv2.imwrite(path, frame)
                    
                    self.temp_photo_path = path
                    
                    # Update preview on the main popup
                    prev_img = Image.open(path)
                    ctk_prev = ctk.CTkImage(light_image=prev_img, dark_image=prev_img, size=(200, 150))
                    self.photo_preview.configure(image=ctk_prev, text="")
                    
                    cap.release()
                    cam_win.destroy()

            ctk.CTkButton(cam_win, text="📸 CAPTURE", command=capture, fg_color="green").pack(pady=10)
            update_cam()

        ctk.CTkButton(win, text="Open Camera", command=take_photo_live).pack(pady=5)

        def save():
            if n.get():
                mid = str(uuid.uuid4())
                file_name = f"cards/{n.get()}.pdf" # Store the path in a variable
                
                with self.db._get_connection() as conn:
                    conn.execute("INSERT INTO members VALUES (?, ?, ?)", 
                                 (mid, n.get(), str(datetime.datetime.now())))
                    conn.commit()
                
                os.makedirs("cards", exist_ok=True)
                self.asset_gen.create_member_card(mid, n.get(), file_name, self.temp_photo_path)
                
                # --- NEW: Automatically Open the PDF ---
                try:
                    os.startfile(os.path.abspath(file_name))
                except Exception as e:
                    print(f"Could not open PDF: {e}")

                # Cleanup temp photo
                if self.temp_photo_path and os.path.exists(self.temp_photo_path):
                    win.after(1000, lambda: os.remove(self.temp_photo_path))
                
                win.destroy()

        ctk.CTkButton(win, text="Create Library Card", command=save, fg_color="#3a7ebf").pack(pady=20)

    def open_member_search(self):
        win = ctk.CTkToplevel(self)
        win.title("Child Records")
        win.geometry("600x600")
        
        # Search area
        f = ctk.CTkFrame(win)
        f.pack(fill="x", padx=10, pady=10)
        s = ctk.CTkEntry(f, placeholder_text="Search by name...")
        s.pack(side="left", expand=True, fill="x", padx=5)
        
        box = ctk.CTkTextbox(win, width=580, height=300, font=("Courier", 12))
        box.pack(pady=5, padx=10)

        def refresh():
            box.configure(state="normal")
            box.delete("0.0", "end")
            search_query = f"%{s.get().strip()}%"
            
            with self.db._get_connection() as conn:
                members = conn.execute("SELECT * FROM members WHERE name LIKE ?", (search_query,)).fetchall()
                
                header = f"{'ID (First 8)':<15} | {'NAME'}\n"
                box.insert("end", header + "="*50 + "\n")
                
                if not members:
                    box.insert("end", "\n   No children found.")
                else:
                    for m in members:
                        short_id = m['id'][:8]
                        box.insert("end", f"{short_id:<15} | {m['name']}\n")
            
                    def reprint_card():
                        pass 

            box.configure(state="disabled")

        # Delete Section
        del_f = ctk.CTkFrame(win)
        del_f.pack(fill="x", padx=10, pady=20)
        del_entry = ctk.CTkEntry(del_f, placeholder_text="Enter ID (8 chars) to delete...")
        del_entry.pack(side="left", expand=True, fill="x", padx=10)

        def delete_member():
            tid = del_entry.get().strip()
            if not tid: return
            
            from tkinter import messagebox
            confirm = messagebox.askyesno("Confirm Delete", f"Delete child record starting with ID: {tid}?")
            
            if confirm:
                with self.db._get_connection() as conn:
                    # Safety Check: Check if child has any active loans
                    active_loan = conn.execute("""
                        SELECT books.title FROM loans 
                        JOIN books ON loans.book_id = books.id 
                        WHERE loans.member_id LIKE ? AND loans.return_date IS NULL
                    """, (f"{tid}%",)).fetchone()
                    
                    if active_loan:
                        messagebox.showerror("Error", f"Cannot delete! This child still has '{active_loan['title']}' checked out.")
                    else:
                        # Delete loan history first (to avoid database errors) then the member
                        conn.execute("DELETE FROM loans WHERE member_id LIKE ?", (f"{tid}%",))
                        conn.execute("DELETE FROM members WHERE id LIKE ?", (f"{tid}%",))
                        conn.commit()
                        del_entry.delete(0, "end")
                        refresh()
                        messagebox.showinfo("Deleted", "Child record removed.")

        ctk.CTkButton(f, text="Search", command=refresh).pack(side="left", padx=5)
        ctk.CTkButton(del_f, text="🗑️ Delete", fg_color="red", command=delete_member).pack(side="right", padx=10)
        
        refresh()

    def open_inventory(self):
        win = ctk.CTkToplevel(self)
        win.title("Inventory")
        win.geometry("800x700")
        
        f = ctk.CTkFrame(win)
        f.pack(fill="x", padx=10, pady=10)
        s = ctk.CTkEntry(f, placeholder_text="Search...")
        s.pack(side="left", expand=True, fill="x", padx=5)
        
        # A little easeir a press enter to search
        s.bind("<Return>", lambda event: refresh())
        
        box = ctk.CTkTextbox(win, width=780, height=350, font=("Courier", 12))
        box.pack(pady=5)

        def refresh():
            box.configure(state="normal")
            box.delete("0.0", "end")
            search_query = f"%{s.get().strip()}%"
            with self.db._get_connection() as conn:
                books = conn.execute("SELECT * FROM books WHERE title LIKE ? OR author LIKE ?", 
                                   (search_query, search_query)).fetchall()
                header = f"{'ID (First 8)':<12} | {'ST':<4} | {'TITLE'}\n"
                box.insert("end", header + "-"*60 + "\n")
                for b in books:
                    short_id = b['id'][:8]
                    st = "🆕" if b['is_printed'] == 0 else "✅"
                    box.insert("end", f"{short_id:<12} | {st:<4} | {b['title']}\n")
            box.configure(state="disabled")

        def print_batch():
            with self.db._get_connection() as conn:
                books = conn.execute("SELECT * FROM books WHERE is_printed = 0").fetchall()
                if not books:
                    from tkinter import messagebox
                    messagebox.showinfo("Info", "No new books to print!")
                    return

                os.makedirs("labels", exist_ok=True)
                file_name = f"labels/Batch_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                
                from reportlab.lib.pagesizes import letter
                pdf_canvas = canvas.Canvas(file_name, pagesize=letter)
                width, height = letter
                
                margin, label_w, label_h = 0.5 * inch, 2.5 * inch, 1.5 * inch
                cols, rows = 3, 6 
                x_cursor, y_cursor = margin, height - margin - label_h
                count = 0

                for b in books:
                    self.asset_gen.draw_label_at(pdf_canvas, b['id'], b['title'], b['author'], x_cursor, y_cursor)
                    conn.execute("UPDATE books SET is_printed = 1 WHERE id = ?", (b['id'],))
                    
                    count += 1
                    if count == len(books): # Don't move cursor if it's the last book
                        break
                        
                    x_cursor += label_w
                    if count % cols == 0:
                        x_cursor = margin
                        y_cursor -= label_h
                    if count % (cols * rows) == 0:
                        pdf_canvas.showPage()
                        x_cursor, y_cursor = margin, height - margin - label_h
                
                pdf_canvas.save()
                conn.commit() 
                
                try:
                    os.startfile(os.path.abspath(file_name))
                except:
                    pass
                refresh()

        ctk.CTkButton(f, text="Search", command=refresh).pack(side="left", padx=5)
        ctk.CTkButton(win, text="Print New Labels (Batch)", fg_color="#2b719e", command=print_batch).pack(pady=10)
        
        delete_frame = ctk.CTkFrame(win)
        delete_frame.pack(fill="x", padx=10, pady=20)
        del_entry = ctk.CTkEntry(delete_frame, placeholder_text="Enter ID (8 chars) to delete...")
        del_entry.pack(side="left", expand=True, fill="x", padx=10)

        def delete_book():
            target_id = del_entry.get().strip()
            if not target_id: return
            from tkinter import messagebox
            
            # Find the actual book first to be safe
            with self.db._get_connection() as conn:
                book = conn.execute("SELECT id, title FROM books WHERE id LIKE ?", (f"{target_id}%",)).fetchone()
                
                if not book:
                    messagebox.showerror("Error", "No book found with that ID.")
                    return

                confirm = messagebox.askyesno("Confirm Delete", f"Delete '{book['title']}'?\n(ID: {book['id']})")
                
                if confirm:
                    on_loan = conn.execute("SELECT * FROM loans WHERE book_id = ? AND return_date IS NULL", (book['id'],)).fetchone()
                    if on_loan:
                        messagebox.showerror("Error", "This book is currently checked out!")
                    else:
                        conn.execute("DELETE FROM books WHERE id = ?", (book['id'],))
                        conn.commit()
                        del_entry.delete(0, "end")
                        refresh()
                        messagebox.showinfo("Deleted", "Book removed.")

        ctk.CTkButton(delete_frame, text="🗑️ Delete", fg_color="red", command=delete_book).pack(side="right", padx=10)
        refresh()

    def open_live_loans(self):
        win = ctk.CTkToplevel(self)
        win.title("Live Loans")
        win.geometry("700x500")
        
        # Search frame (Optional: filter by child name or book title)
        f = ctk.CTkFrame(win)
        f.pack(fill="x", padx=10, pady=10)
        s = ctk.CTkEntry(f, placeholder_text="Search active loans...")
        s.pack(side="left", expand=True, fill="x", padx=5)

        box = ctk.CTkTextbox(win, width=680, height=400, font=("Courier", 12))
        box.pack(pady=10, padx=10)

        def refresh():
            box.configure(state="normal")
            box.delete("0.0", "end")
            
            # Search filter for loans
            search_term = f"%{s.get().strip()}%"
            
            query = """
                SELECT books.title, members.name, loans.checkout_date, loans.due_date
                FROM loans
                JOIN books ON loans.book_id = books.id
                JOIN members ON loans.member_id = members.id
                WHERE loans.return_date IS NULL 
                AND (books.title LIKE ? OR members.name LIKE ?)
                ORDER BY loans.checkout_date DESC
            """
            
            with self.db._get_connection() as conn:
                loans = conn.execute(query, (search_term, search_term)).fetchall()
                
                header = f"{'BOOK TITLE':<25} | {'BORROWER':<18} | {'DUE DATE'}\n"
                box.insert("end", header + "="*65 + "\n")
                
                if not loans:
                    box.insert("end", "\n   🎉 No books are currently checked out!")
                else:
                    for l in loans:
                        # Simple logic to check if overdue
                        due_date = str(l['due_date'])[:10]
                        box.insert("end", f"{l['title'][:23]:<25} | {l['name'][:16]:<18} | {due_date}\n")
            
            box.configure(state="disabled")

        # Connect the search button and Enter key to the refresh
        ctk.CTkButton(f, text="Search", command=refresh).pack(side="left", padx=5)
        s.bind("<Return>", lambda event: refresh())

        # Initial load
        refresh()
        
        def print_batch():
            with self.db._get_connection() as conn:
                # Get all books that haven't been printed yet
                books = conn.execute("SELECT * FROM books WHERE is_printed = 0").fetchall()
        
                if books:
                    os.makedirs("labels", exist_ok=True)
                    file_name = f"labels/Batch_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            
                    # Set page to standard Letter size
                    from reportlab.lib.pagesizes import letter
                    c = canvas.Canvas(file_name, pagesize=letter)
                    width, height = letter # 8.5 x 11 inches
            
                    # Define Grid Settings
                    margin = 0.5 * inch
                    label_w, label_h = 2.5 * inch, 1.5 * inch
                    cols, rows = 3, 6 # 3 labels across, 6 labels down
            
                    x_cursor, y_cursor = margin, height - margin - label_h
                    count = 0

                    for b in books:
                        # Draw the label at the current grid position
                        # We update draw_label to take x and y coordinates
                        self.asset_gen.draw_label_at(c, b['id'], b['title'], b['author'], x_cursor, y_cursor)
                
                        # Update database so we don't print it again next time
                        conn.execute("UPDATE books SET is_printed = 1 WHERE id = ?", (b['id'],))
                
                        # Move to the next column
                        count += 1
                        x_cursor += label_w
                
                        # If we hit the end of the row, move down to the next row
                        if count % cols == 0:
                            x_cursor = margin
                            y_cursor -= label_h
                
                        # If the page is full, start a new page
                        if count % (cols * rows) == 0:
                            c.showPage()
                            x_cursor, y_cursor = margin, height - margin - label_h
            
                    c.save()

        ctk.CTkButton(f, text="Search", command=refresh).pack(side="left", padx=5)
        ctk.CTkButton(win, text="Print New Labels (Batch)", command=print_batch).pack(pady=10)
        refresh()

if __name__ == "__main__":
    app = LibraryApp(); app.mainloop()
