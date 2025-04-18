"""
check_update.py - Modulo per verificare gli aggiornamenti del launcher su GitHub
"""

import logging
import requests
import re
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List

from version import VERSION, GITHUB_API_URL

class UpdateChecker(QThread):
    """Thread per controllare la disponibilità di aggiornamenti su GitHub"""
    
    # Segnali per comunicare i risultati
    update_available = pyqtSignal(str, str, str)  # Versione, URL, Data rilascio
    no_update_available = pyqtSignal()
    check_error = pyqtSignal(str)  # Messaggio di errore
    
    def __init__(self):
        super().__init__()
        self.current_version = VERSION
        self._is_running = True
        self.setObjectName("UpdateCheckerThread")
    
    def stop(self):
        """Richiede l'interruzione dell'operazione"""
        logging.info(f"Richiesta interruzione per {self.objectName()}")
        self._is_running = False
    
    def run(self):
        """Esegue il controllo degli aggiornamenti contattando l'API GitHub"""
        logging.info(f"Avvio {self.objectName()} - Controllo aggiornamenti")
        
        try:
            # Prepara gli headers per l'API GitHub
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"GodotLauncher/{VERSION}"
            }
            
            # Contatta l'API GitHub
            logging.info(f"Richiesta API GitHub: {GITHUB_API_URL}")
            response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Controlla se la risposta è valida
            releases = response.json()
            if not isinstance(releases, list) or not releases:
                raise ValueError("Formato risposta API non valido o nessuna release trovata")
            
            # Trova le release con tag validi (escludendo pre-release se necessario)
            valid_releases = []
            for release in releases:
                # Considera solo release pubblicate (non bozze)
                if release.get("draft", True):
                    continue
                    
                tag = release.get("tag_name", "")
                # Rimuovi eventuali prefissi (come "v") per il confronto numerico
                cleaned_tag = tag.lstrip("vV") if tag else ""
                
                if not cleaned_tag:
                    continue
                
                valid_releases.append({
                    "tag": tag,
                    "cleaned_tag": cleaned_tag,
                    "url": release.get("html_url", ""),
                    "published_at": release.get("published_at", ""),
                    "prerelease": release.get("prerelease", False)
                })
            
            if not valid_releases:
                logging.info("Nessuna release valida trovata")
                self.no_update_available.emit()
                return
            
            # Ordina le release per versione (più recente prima)
            valid_releases.sort(key=lambda r: r["published_at"], reverse=True)
            
            # Confronta la versione corrente con l'ultima versione stabile
            current_version_cleaned = self.current_version.lstrip("vV")
            latest_release = valid_releases[0]
            
            if self._is_newer_version(latest_release["cleaned_tag"], current_version_cleaned):
                logging.info(f"Nuova versione disponibile: {latest_release['tag']}")
                
                # Formatta la data di pubblicazione
                published_date = ""
                if latest_release["published_at"]:
                    try:
                        dt = datetime.fromisoformat(latest_release["published_at"].replace("Z", "+00:00"))
                        published_date = dt.strftime("%d/%m/%Y")
                    except (ValueError, TypeError):
                        published_date = latest_release["published_at"]
                
                self.update_available.emit(
                    latest_release["tag"],
                    latest_release["url"],
                    published_date
                )
            else:
                logging.info("Nessun aggiornamento disponibile")
                self.no_update_available.emit()
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Errore di rete durante il controllo aggiornamenti: {e}"
            logging.error(error_msg)
            self.check_error.emit(error_msg)
        except Exception as e:
            error_msg = f"Errore durante il controllo aggiornamenti: {e}"
            logging.exception(error_msg)
            self.check_error.emit(error_msg)
        finally:
            logging.info(f"{self.objectName()} terminato")
    
    def _is_newer_version(self, latest_version: str, current_version: str) -> bool:
        """
        Confronta due stringhe di versione per determinare se latest_version è più recente
        di current_version. Gestisce formati di versione semantica (es. 1.2.3, 1.2.3-dev1).
        
        Returns:
            True se latest_version è più recente di current_version, False altrimenti
        """
        try:
            # Separa la versione principale (1.2.3) da eventuali suffissi (dev1, beta2, ecc.)
            def parse_version(version_str: str) -> Tuple[List[int], str]:
                # Separa la versione numerica da eventuali suffissi
                match = re.match(r"^(\d+(?:\.\d+)*)(?:-(.+))?$", version_str)
                if not match:
                    return [0], ""  # Fallback per format non riconosciuti
                
                version_numbers = [int(x) for x in match.group(1).split(".")]
                suffix = match.group(2) or ""
                return version_numbers, suffix
            
            latest_nums, latest_suffix = parse_version(latest_version)
            current_nums, current_suffix = parse_version(current_version)
            
            # Confronta i numeri di versione
            for latest, current in zip(latest_nums, current_nums):
                if latest > current:
                    return True
                if latest < current:
                    return False
            
            # Se arriviamo qui, i numeri di versione sono uguali o current ha più segmenti
            if len(latest_nums) > len(current_nums):
                return True
            if len(latest_nums) < len(current_nums):
                return False
            
            # A questo punto, i numeri di versione sono identici, confronta i suffissi
            # Nessun suffisso è considerato "più stabile/recente" di qualsiasi suffisso
            if not latest_suffix and current_suffix:
                return True
            if latest_suffix and not current_suffix:
                return False
            
            # Confronta alfabeticamente i suffissi (imperfetto ma semplice)
            # Idealmente dovremmo fare un'analisi più sofisticata per comparare
            # suffissi come "alpha1" vs "beta2" vs "rc1", ma per ora va bene così
            return latest_suffix > current_suffix
            
        except Exception as e:
            logging.error(f"Errore durante il confronto versioni: {e}")
            # In caso di errore, assumiamo che non ci sia un aggiornamento
            return False

def check_for_update() -> QThread:
    """
    Funzione di utilità per avviare il controllo aggiornamenti.
    
    Returns:
        L'istanza del thread UpdateChecker avviato
    """
    checker = UpdateChecker()
    checker.start()
    return checker 