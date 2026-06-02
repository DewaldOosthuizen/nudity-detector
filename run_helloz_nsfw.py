#!/usr/bin/env python3
"""Launcher for the Helloz NSFW CLI detector."""
import logging

from src.detectors.helloz_nsfw import main

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
