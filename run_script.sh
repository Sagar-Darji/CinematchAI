#!/bin/bash
# Simple wrapper to run scripts with PYTHONPATH set

export PYTHONPATH="/Users/sagardarji/CinematchAI:$PYTHONPATH"
python "$@"
