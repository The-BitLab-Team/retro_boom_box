"""Entrada usada para montar o RetroBoomBox.exe (o PyInstaller precisa de um arquivo, não de `-m`)."""
import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
