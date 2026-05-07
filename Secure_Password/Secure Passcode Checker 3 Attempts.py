import getpass
import os # We'll use this to check if the file exists

# --- GLOBAL CONFIGURATION ---
PASSCODE_FILE = "passcode.txt"

def load_passcode():
    """Attempts to load the passcode from a file."""
    if os.path.exists(PASSCODE_FILE):
        try:
            with open(PASSCODE_FILE, 'r') as f:
                # Read the first line and convert to integer
                return int(f.read().strip()), True
        except ValueError:
            print("Error: Passcode file corrupted. Cannot load.")
            return None, False
        except Exception as e:
            print(f"Error loading passcode: {e}")
            return None, False
    else:
        # File does not exist (first run)
        return None, False

def save_passcode(code):
    """Saves the new passcode to the file."""
    try:
        with open(PASSCODE_FILE, 'w') as f:
            f.write(str(code))
        print(f"Passcode saved successfully to {PASSCODE_FILE}.")
    except Exception as e:
        print(f"Error saving passcode: {e}")

# --- MAIN PROGRAM START ---
passcode, file_exists = load_passcode()

if passcode is None and not file_exists:
    print("\n--- FIRST RUN: NO PASSCODE FOUND ---")
    print("You must set a new passcode to use the system.")
    must_set_passcode = True
elif passcode is None and file_exists:
    # This covers the file corrupted case
    print("Due to file corruption, system cannot proceed. Please delete passcode.txt to reset.")
    exit()
else:
    # Passcode was successfully loaded
    print(f"\nPasscode successfully loaded from {PASSCODE_FILE}.")
    must_set_passcode = False


passcode_was_set_this_run = False # Flag to track if the passcode was successfully set/changed
access_mode = 'check' # Default action is to check access

# If no passcode was loaded, the only option is to set one.
if must_set_passcode:
    initial_command = 'set passcode'
    print("Automatically entering 'set passcode' mode.")
else:
    # If a passcode exists, ask the user what to do
    initial_command = input("Type 'set passcode' to change it, or press Enter to check access: ").strip().lower()

# Process the command
if initial_command == 'set passcode':
    print("\n--- Passcode Change Mode ---")
    
    # --- STEP 1: VERIFY CURRENT PASSCODE ---
    verified = False
    
    # Loop for current password verification
    while not verified:
        try:
            # Use the loaded or default passcode for verification
            current_check_str = getpass.getpass("Enter CURRENT passcode to authorize change (Input Hidden): ")
            current_check = int(current_check_str)
            
            if current_check == passcode:
                verified = True
                print("Current Passcode verified. Proceeding to set new passcode.")
            else:
                print("Incorrect CURRENT Passcode. Cannot proceed with change.")
                # We exit setup mode if current passcode is wrong
                break 
        except ValueError:
            print("Invalid input (numbers only). Please try again.")

    # --- STEP 2: SET AND CONFIRM NEW PASSCODE (Only runs if verified is True) ---
    if verified:
        # Loop for setting and confirming the new passcode
        while True:
            try:
                # 1. Get the new passcode (Input Hidden)
                new_passcode_1_str = getpass.getpass("Set NEW passcode (numbers only, Input Hidden): ")
                new_passcode_1 = int(new_passcode_1_str)
                
                # 2. Get the confirmation passcode (Input Hidden)
                new_passcode_2_str = getpass.getpass("Confirm new passcode (type it again, Input Hidden): ")
                new_passcode_2 = int(new_passcode_2_str)
                
                # 3. Check for match
                if new_passcode_1 == new_passcode_2:
                    passcode = new_passcode_1 # Update the in-memory passcode
                    save_passcode(passcode) # <-- NEW: Save to file
                    passcode_was_set_this_run = True 
                    break # Exit the setup loop
                else:
                    print("Passcodes did not match. Please try setting it again.")
                    
            except ValueError:
                print("Invalid input. Passcode must be numbers only. Please try again.")
    
# --- Start the Access Check Process (if a passcode exists) ---

if passcode is not None:
    print("\n--- Access Check Mode ---")
    
    # 2. Check the Passcode - Allow up to 3 attempts
    attempts = 0
    max_attempts = 3
    access_granted = False

    while attempts < max_attempts:
        try:
            # Ask user for the passcode (Input Hidden)
            check_code_str = getpass.getpass(f"Enter Passcode to continue. (Attempt {attempts + 1} of {max_attempts}, Input Hidden): ")
            check_code = int(check_code_str)

            # Compare against the saved passcode
            if check_code == passcode:
                print("Access Granted")
                access_granted = True
                break # Exit the while loop immediately upon success
            else:
                attempts += 1
                if attempts < max_attempts:
                    print(f"Wrong Password. You have {max_attempts - attempts} attempts left.")

        except ValueError:
            attempts += 1
            if attempts < max_attempts:
                print(f"Invalid input (numbers only). You have {max_attempts - attempts} attempts left.")

    # 3. Final Result
    if not access_granted:
        print("Too many wrong attempts. Access Denied.")
else:
    print("\nNo valid passcode exists. System is inaccessible.")
    
print("Good bye")
