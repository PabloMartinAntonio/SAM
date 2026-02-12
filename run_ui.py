"""
Entrypoint para la UI de Speech Analytics.
Ejecutar: python run_ui.py
"""
import sys
from ui.app import SpeechAnalyticsApp

def main():
    try:
        app = SpeechAnalyticsApp()
        app.run()
    except Exception as e:
        print(f"Error fatal al iniciar UI: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
