# Passcode checker allow 3 attempts, hashed and salted, and hid typeing
# By Grant Ruffner

import getpass
import os        
import hashlib

PASSCODE_FILE = "passcode.txt"
ENCODING = 'utf-8'
def load_passcode():
    if os.path.exists(PASSCODE_FILE):
        try:
            with open(PASSCODE_FILE, 'r') as f:
                content = f.read().strip()
                if ':' in content:
                    hashed_code, salt = content.split(':', 1)
                    return hashed_code, salt, True
                else:
                    return None, None, True
        except Exception as e:
            print(f"Something went wrong loading passcode file: {e}")
            return None, None, False
    else:
        return None, None, False
def hash_passcode(code_str, salt):
    salted_code = salt + code_str
    encoded_code = salted_code.encode(ENCODING)
    return hashlib.sha256(encoded_code).hexdigest()
def save_passcode(hashed_code, salt):
    try:
        with open(PASSCODE_FILE, 'w') as f:
            f.write(f"{hashed_code}:{salt}")
        print(f"Passcode with hash and salt saved successfully to {PASSCODE_FILE}.")
    except Exception as e:
        print(f"Something went wrong saving passcode: {e}")
passcode_hash, salt_stored, file_exists = load_passcode()
if passcode_hash is not None and file_exists:
    print(f"\nPasscode hash and salt successfully loaded from {PASSCODE_FILE}.")
passcode_was_set_this_run = False
if passcode_hash is None and not file_exists:
    print("\n--- This is your first time running cause no passcode was found")
    print("You must set a new passcode to start using")
    initial_command = 'set passcode'
elif passcode_hash is None and file_exists:
    print("Well the file is wrong somehow. Go to app dir and delete the passcode.txt to fix.")
    exit()
if initial_command == 'set passcode':
    print("\n--- Passcode Changing/Setup Mode ---")
    if passcode_hash is None:
        verified = True
        print("Hey we have to set a passcode first.")
    else:
        verified = False
        while not verified:
            try:
                current_check_str = getpass.getpass("If you want to change this passcode enter current one first. --== typing is always hidden ==--")
                current_check_hash = hash_passcode(current_check_str, salt_stored) 
                if current_check_hash == passcode_hash:
                    verified = True
                    print("Ok you got it. Lets change that to a new passcode.")
                else:
                    print("If you don't know passcode then you can't change it.")
                    break 
            except Exception:
                print("Opps an error accured. Please try again.")
    if verified:
        while True:
            try:
                new_passcode_1_str = getpass.getpass("Set your passcode --== Don't worry typing is hid ==--: ")
                new_passcode_2_str = getpass.getpass("Retype it to make sure you got it down --== Again don't worry typing is hid ==--: ")
                if new_passcode_1_str == new_passcode_2_str:
                    new_salt = os.urandom(16).hex() 
                    new_passcode_hash = hash_passcode(new_passcode_1_str, new_salt)
                    passcode_hash = new_passcode_hash
                    salt_stored = new_salt
                    save_passcode(passcode_hash, salt_stored) 
                    passcode_was_set_this_run = True 
                    print("Yay! You just saved your passcode hashed and salted.")
                    break
                else:
                    print("Passcodes not the same. Please retype it again.") 
            except Exception:
                print("Opps an error accured. Please try again.")
if passcode_hash is not None: 
    print("\n--- Entering the check stage ---")
    attempts = 0
    max_attempts = 3
    access_granted = False
    while attempts < max_attempts:
        try:
            check_code_str = getpass.getpass(f"Enter Passcode to continue. (Your on {attempts + 1} try of {max_attempts}, --== And don't worry typing is hid ==--): ")        
            check_code_hash = hash_passcode(check_code_str, salt_stored)
            if check_code_hash == passcode_hash:
                print("Access allowed")
                access_granted = True
                break
            else:
                attempts += 1
                if attempts < max_attempts:
                    print(f"You typed something wrong. You have {max_attempts - attempts} trys left.")
        except Exception:
            attempts += 1
            if attempts < max_attempts:
                print(f"Do you even know the passcode. You have {max_attempts - attempts} trys left.")
    if not access_granted:
        print("Wrong again out of tries. Access not granted.")
else:
    print("\nSorry No Passcode there. Exiting Checker")
print("Good bye")
