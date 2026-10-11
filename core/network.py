# -*- coding: utf-8 -*-
"""Detecção de caminhos de rede e validação assíncrona do banco."""

from __future__ import annotations

import sys
import threading

from PyQt6.QtCore import QThread, pyqtSignal


def is_network_path(path: str) -> bool:
    """Detecta se o caminho é uma unidade de rede (UNC ou mapeada)."""
    if not path:
        return False
    
    # UNC path (\\servidor\compartilhamento)
    if path.startswith('\\\\') or path.startswith('//'):
        return True
    
    # Verificar se é unidade mapeada (Windows)
    if sys.platform == 'win32' and len(path) >= 2 and path[1] == ':':
        try:
            import subprocess
            drive_letter = path[0].upper()
            result = subprocess.run(['net', 'use'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and drive_letter in result.stdout:
                return True
        except Exception:
            pass
    
    return False


class AsyncDatabaseValidator(QThread):
    """Thread para validar banco de dados de forma assíncrona (evita travar UI)."""
    finished = pyqtSignal(bool, str, str)  # (is_valid, message, file_path)
    progress = pyqtSignal(str)  # mensagem de progresso
    
    def __init__(self, file_path: str, timeout: int = 15):
        super().__init__()
        self.file_path = file_path
        self.timeout = timeout
        self._stop = False
        
    def stop(self):
        """Sinaliza para parar a validação."""
        self._stop = True
        
    def run(self):
        """Executa validação com timeout."""
        try:
            if self._stop:
                return
                
            self.progress.emit("Verificando arquivo...")
            
            # Timeout usando QTimer (funciona melhor com Qt)
            import threading
            result = [None, None]  # [is_valid, message]
            exception = [None]
            
            def validate_with_timeout():
                try:
                    if self._stop:
                        return
                    from core.config import validate_database_path
                    result[0], result[1] = validate_database_path(self.file_path)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=validate_with_timeout, daemon=True)
            thread.start()
            thread.join(timeout=self.timeout)
            
            if self._stop:
                return
                
            if thread.is_alive():
                # Timeout atingido
                self.finished.emit(
                    False,
                    f"⏱️ Timeout ao validar banco de dados ({self.timeout}s).\n\nO arquivo pode estar em rede lenta ou inacessível.",
                    self.file_path
                )
                return
            
            if exception[0]:
                raise exception[0]
                
            if result[0] is None:
                raise Exception("Validação não retornou resultado")
                
            self.finished.emit(result[0], result[1] or "Validado", self.file_path)
            
        except Exception as e:
            if not self._stop:
                self.finished.emit(False, f"Erro ao validar: {str(e)}", self.file_path)
