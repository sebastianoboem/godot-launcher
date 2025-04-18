"""
version.py - Contiene informazioni sulla versione del Godot Launcher
"""

# Versione attuale del launcher - modifica qui per aggiornare la versione dell'applicazione
VERSION = "v1.0.0-dev1"

# Nome del repository GitHub per controllare gli aggiornamenti
GITHUB_REPO = "sebastianoboem/godot-launcher"

# URL della pagina delle release
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"

# URL dell'API GitHub per le release
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

# Funzione per ottenere la versione corrente
def get_version():
    return VERSION 