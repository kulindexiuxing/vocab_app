#!/bin/bash
until curl -s http://localhost:5001 > /dev/null 2>&1; do
    sleep 1
done
open http://localhost:5001
