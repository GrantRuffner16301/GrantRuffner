checkit = int(input("Enter a maximum number: "))

primes = [num for num in range(2, checkit + 1) if all(num % i != 0 for i in range(2, int(num**0.5) + 1))]

print(f"Listing prime numbers up to {checkit}:")
for p in primes:
 print(p)