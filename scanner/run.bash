#!/bin/bash

cd {RUNNER_HOME_DIR}/.bashrc

cd {SCANNER_UP_PATH}

source .venv/bin/activate
python main.py
