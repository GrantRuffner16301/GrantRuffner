# first we call the built in random module to save lots of typing
import random
# now we want to difine a new function we can call on later to start our game
def simple_guess_the_number(): # now we have a way to start the game by calling this
    # need to set a few varialbes for saving some values we need saved
    MIN_NUMBER = 1
    MAX_NUMBER = 25
    MAX_GUESSES = 3
    
    # start a loop for the game play
    while True:
        # now we call the random module to do its job and give us a random number
        WINNING_NUMBER = random.randint(MIN_NUMBER, MAX_NUMBER)
        # fun fact there is no such thing as a random number to a computer

        # ask user if they want to play and give rules to game
        print("Want to play a Game?")
        print("You get 3 tries and 2 hints of higher or lower.")
        print(f"To guess my number between {MIN_NUMBER} and {MAX_NUMBER}.")

        # here the game loop is at work for MAX_GUESSES
        for guess_count in range(1, MAX_GUESSES + 1):

        # lets get users input and make sure its a number like error handling
            while True:
                try:
                    user_input = input(f"guess {guess_count}: What is your guess?")
                    user_guess = int(user_input)
                    break

                # Scold for entering letter 
                except ValueError:
                    print("Come on quit messing aroung guess a number.")

        # lets test users answer 
        if user_guess == WINNING_NUMBER:
                print(f"\nHow did a human guess ({WINNING_NUMBER}) in {guess_count} tries!")
                # they got it leave guess loop but stay in game
                break

        if guess_count < MAX_GUESSES:
            if user_guess < WINNING_NUMBER:
                print("Your too Low. Guess higher.")
            
            else: # only one choice left now save yourself time its redundent don't type it out
                print("Your too High. Guess lower.")

       # tell me i didn't get the number # simple_guess_the_number()
        else:
            print(f"You suck at this! It ws {WINNING_NUMBER}.")

       # lets see if we want to keep playing
        play_again = input("play again sucker? (y/n): ").strip().lower()
        if play_again != 'y': # if y then restart if not finish /end game 
           print("Whatever didn't think it was in you! Good day.")
           break

