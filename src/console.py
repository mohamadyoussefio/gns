import sys
import time
import threading

class ConsoleSpinner:
    def __init__(self, message="Working..."):
        self.message = message
        # Smooth Unicode braille spinner frames
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.running = False
        self.thread = None

    def _spin(self):
        idx = 0
        while self.running:
            # Subtle bold blue frame indicator with dimmed description text
            sys.stdout.write(f"\r\033[1;34m{self.frames[idx]}\033[0m \033[2m{self.message}\033[0m")
            sys.stdout.flush()
            idx = (idx + 1) % len(self.frames)
            time.sleep(0.08)

    def __enter__(self):
        # Only start the background spinner thread if stdout is a live TTY terminal
        if sys.stdout.isatty():
            self.running = True
            self.thread = threading.Thread(target=self._spin, daemon=True)
            self.thread.start()
        return self

    def update_message(self, new_message):
        self.message = new_message

    def __exit__(self, exc_type, exc_val, exc_tb):
        if sys.stdout.isatty():
            self.running = False
            if self.thread:
                self.thread.join()
            # Clean current line on exit
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

def print_success(message):
    # Dimmed text with a clean green checkmark
    print(f"\r\033[32m✔\033[0m {message}")

def print_warning(message):
    # Dimmed text with a clean orange warning icon
    print(f"\r\033[33m⚠\033[0m {message}")

def print_error(message):
    # Clean red cross icon
    print(f"\r\033[31m✖\033[0m {message}")

def print_info(message):
    # Clean blue info icon
    print(f"\r\033[34mℹ\033[0m {message}")

def print_section(title):
    # Sleek, minimalist section header with high-contrast magenta indicator
    print(f"\n\033[1;35m◆\033[0m \033[1m{title.upper()}\033[0m")
