#!/usr/bin/env python3
"""
AIOps Main Entry Point - Autonomous Incident Management System
"""
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

if __name__ == '__main__':
    from cli.aiops_cli import cli
    cli()