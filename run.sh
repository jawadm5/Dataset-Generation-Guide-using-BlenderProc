#!/usr/bin/env bash
#
# run10.sh — run blenderproc on mycode.py 10 times, continue even on failures

# Loop from 1 to 2000
for i in {1..2000}; do
  echo "======================================"
  echo " Starting BlenderProc run #$i at $(date +'%Y-%m-%d %H:%M:%S')"
  echo "======================================"

  # Run BlenderProc and capture its exit code
  blenderproc run husky.py
  code=$?
  echo "Continuing to next run."

  echo
done

echo "All runs attempted!"