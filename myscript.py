# myscript.py
import sys

def greet(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = greet(sys.argv[1])
        print(result)
    else:
        print("No function specified")
