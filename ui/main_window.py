# main_window.py
# Janela principal do sistema (shell)

from PyQt6.QtWidgets import QMainWindow

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Confeitaria Pro")
        # TODO: Adicionar inicialização de layout, sidebar, header, páginas
