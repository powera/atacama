from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import re
from typing import Dict, List
from flask import Flask, request, jsonify
import logging
from waitress import serve
import imaplib
import email
import threading
import time
import os
from email.header import decode_header
import json

app = Flask(__name__)
Base = declarative_base()

# [Previous ColorScheme and Email classes remain the same]

if __name__ == "__main__":
    run_server()
