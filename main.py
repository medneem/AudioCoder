"""AudioCoder desktop entry point."""
from multiprocessing import freeze_support
from audiocoder.ui import AudioCoderApp

if __name__ == "__main__":
    freeze_support()
    AudioCoderApp().mainloop()
