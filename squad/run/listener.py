import os
import sys


def main():
    argv = [
        sys.executable, '-m', 'squad.manage', 'listen'
    ] + sys.argv[1:]
    os.execvp(sys.executable, argv)


if __name__ == "__main__":
    main()
