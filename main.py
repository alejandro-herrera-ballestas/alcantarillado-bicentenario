"""
Abre la ventana y carga automáticamente ``data/DataSetBicentenario.xlsx`` si existe.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))      # para poder hacer "import bicentenario"


def main() -> None:
    import tkinter as tk

    from bicentenario.view.main_window import MainWindow

    root = tk.Tk()
    MainWindow(root, default_data=ROOT / "data" / "DataSetBicentenario.xlsx")
    root.mainloop()


if __name__ == "__main__":
    main()
