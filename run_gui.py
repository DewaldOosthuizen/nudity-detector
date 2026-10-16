#!/usr/bin/env python3
"""Launcher for the Nudity Detector GUI application."""

if __name__ == '__main__':
    import multiprocessing

    multiprocessing.freeze_support()

    from src.gui.app import main

    main()
