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
from flask import g

# Local imports
# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

import constants

# Models and database
from models import db
from models.messages import get_message_by_id, get_message_chain, get_filtered_messages
from models.users import get_or_create_user

# Common libraries
from common.config.channel_config import get_channel_manager
import aml_parser
import web.server  # create_app

# Utils
from util import db as db_util
from util import export as export_util

constants.init_production()

app = web.server.create_app()
app_context = app.app_context()
app_context.push()

def set_user(email, name=None):
    """Set the current user for the interactive session."""
    if name is None:
        name = email.split('@')[0]

    user_dict = {"email": email, "name": name}

    with db.session() as db_session:
        db_session.expire_on_commit = False
        g.user = get_or_create_user(db_session, user_dict)

    print(f"Switched to user: {email}")

set_user("atacama@earlyversion.com")

print("\n--- Atacama Interactive Shell ---")
print("Available objects: " + ", ".join(locals().keys()))
