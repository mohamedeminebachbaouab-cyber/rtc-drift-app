#!/usr/bin/env python3
"""
RTC Test Web Application Entry Point
=====================================

Lance l'application RTC Drift Test en mode web pur.
Ouvre automatiquement le navigateur vers l'application.

Usage:
    python run.py                  # Lance sur http://localhost:8050 (navigateur s'ouvre auto)
    python run.py --host 0.0.0.0  # Lance sur http://0.0.0.0:8050 (accessible de partout)
    python run.py --port 5000      # Lance sur http://localhost:5000

Variables d'environnement:
    RCC_HOST (défaut: 0.0.0.0)  - Interface réseau à utiliser
    RCC_PORT (défaut: 8050)     - Port TCP
    
Exemples:
    RCC_PORT=5000 python run.py
    RCC_HOST=127.0.0.1 RCC_PORT=8000 python run.py
"""

import argparse
import os
import sys
import logging
import webbrowser
import time

# Ajouter le répertoire courant au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_web import main

logging.basicConfig(
    stream=sys.stdout,
    force=True,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RTC Drift Test Web Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Interface réseau (défaut: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port TCP (défaut: 8050)",
    )
    
    args = parser.parse_args()
    
    if args.host:
        os.environ["RCC_HOST"] = args.host
    if args.port:
        os.environ["RCC_PORT"] = str(args.port)
    
    # Calculer l'URL avant de lancer le serveur
    port = int(os.environ.get("RCC_PORT", 8050))
    host = os.environ.get("RCC_HOST", "0.0.0.0")
    
    # Pour l'ouverture du navigateur, utiliser localhost même si le serveur écoute sur 0.0.0.0
    browser_url = f"http://localhost:{port}"
    
    logger.info("=" * 60)
    logger.info("RTC Drift Test - Application Web")
    logger.info("=" * 60)
    logger.info(f"Ouverture automatique du navigateur vers {browser_url}")
    
    # Ouvrir le navigateur
    try:
        webbrowser.open(browser_url)
        logger.info("Navigateur ouvert avec succès")
    except Exception as e:
        logger.warning(f"Impossible d'ouvrir automatiquement le navigateur : {e}")
        logger.info(f"Ouvrez manuellement : {browser_url}")
    
    # Petite pause pour laisser le navigateur s'ouvrir
    time.sleep(1)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Arrêt du serveur.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erreur : {e}", exc_info=True)
        sys.exit(1)
