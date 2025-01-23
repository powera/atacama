#!/usr/bin/python3

"""Imports for an interactive session."""

# Stdlib imports
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys

# Third party imports
from flask import session, g

# Local imports
# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

import constants

# common libraries
from common.channel_config import get_channel_manager
from common.database import db
import common.messages
import common.models
import parser

# scripts
import util.db
import util.export

constants.init_production()

print("\n--- Atacama Interactive Shell ---")
print("Available objects: " + ", ".join(locals().keys()))
