# a simple way to check if a string has a palindrome in it.
# by Grant Ruffner

 # first we set variable and give it a value in the form of a word or string.
checkit = "racecar"

# then we check if that word or string is equal to its backwards or reversed pretty much.
if checkit == checkit[::-1]:
    print("Yep a palindrome") #if that word is the same backwards then print it to terminal.
else:
    print("Nope not a palindrome.") #if not then print its not in terminal