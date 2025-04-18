# -*- coding: utf-8 -*-
# validators.py

import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

def is_valid_url(url: str) -> bool:
    """Verifica se una stringa è un URL valido (http o https).

    Args:
        url: La stringa da validare.

    Returns:
        True se l'URL è valido, False altrimenti.
    """
    if not isinstance(url, str):
        return False
    try:
        result = urlparse(url)
        # Controlla che ci siano scheme (http/https) e netloc (dominio)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except ValueError:
        # urlparse potrebbe lanciare ValueError per formati molto errati
        logging.debug(f"ValueError during URL validation for: {url}")
        return False
    except Exception as e:
        # Cattura altri errori imprevisti durante il parsing
        logging.error(f"Unexpected error validating URL '{url}': {e}")
        return False

# Alias per mantenere consistenza con gli altri nomi di funzioni
validate_url = is_valid_url

def validate_project_name(name: str) -> bool:
    """Verifica se un nome progetto è valido.
    
    Args:
        name: Il nome del progetto da validare.
        
    Returns:
        True se il nome è valido, False altrimenti.
    """
    if not isinstance(name, str) or not name:
        return False
    
    # Verifica lunghezza (max 100 caratteri è un limite ragionevole)
    if len(name) > 100:
        return False
    
    # Caratteri non consentiti nei nomi dei file/cartelle
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    return not any(c in name for c in invalid_chars)

def validate_path_exists(path: str) -> bool:
    """Verifica se un percorso esiste.
    
    Args:
        path: Il percorso da validare.
        
    Returns:
        True se il percorso esiste, False altrimenti.
    """
    if not isinstance(path, str) or not path:
        return False
    
    try:
        return os.path.exists(path)
    except Exception as e:
        logging.error(f"Error checking path existence '{path}': {e}")
        return False

def validate_version_string(version: str) -> bool:
    """Verifica se una stringa rappresenta una versione valida.
    
    Accetta formati come "1.0.0", "2.5.7-beta", ecc.
    
    Args:
        version: La stringa di versione da validare.
        
    Returns:
        True se la versione è valida, False altrimenti.
    """
    if not isinstance(version, str) or not version:
        return False
    
    # Pattern per versioni semantiche (semver): X.Y.Z con possibili suffissi
    # Supporta anche versioni come 1.0.0-beta, 1.0.0-alpha.1, ecc.
    pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$'
    return bool(re.match(pattern, version))

def validate_directory_writable(directory: str) -> bool:
    """Verifica se una directory esiste ed è scrivibile.
    
    Args:
        directory: Il percorso della directory da validare.
        
    Returns:
        True se la directory esiste ed è scrivibile, False altrimenti.
    """
    if not isinstance(directory, str) or not directory:
        return False
    
    try:
        path = Path(directory)
        # Verifica se la directory esiste
        if not path.exists() or not path.is_dir():
            return False
            
        # Verifica se la directory è scrivibile provando a creare un file temporaneo
        temp_file = path / f"temp_write_test_{os.getpid()}.tmp"
        try:
            temp_file.touch()
            temp_file.unlink()  # Rimuove il file temporaneo
            return True
        except (PermissionError, OSError):
            return False
    except Exception as e:
        logging.error(f"Error checking directory writeability '{directory}': {e}")
        return False

def validate_godot_project(path: str) -> bool:
    """Verifica se un percorso contiene un progetto Godot valido.
    
    Args:
        path: Il percorso del progetto da validare.
        
    Returns:
        True se il percorso contiene un progetto Godot valido, False altrimenti.
    """
    if not isinstance(path, str) or not path:
        return False
    
    try:
        project_path = Path(path)
        
        # Verifica se la directory esiste
        if not project_path.exists() or not project_path.is_dir():
            return False
            
        # Verifica la presenza del file project.godot
        project_file = project_path / "project.godot"
        return project_file.exists() and project_file.is_file()
    except Exception as e:
        logging.error(f"Error validating Godot project at '{path}': {e}")
        return False

# --- Add more validation functions here if needed --- 