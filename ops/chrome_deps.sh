#!/bin/bash
# ffmpeg, fonts and the libraries Remotion's headless Chrome needs on ubuntu-latest
set -e
sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg fonts-liberation libnss3 libdbus-1-3 libgbm1 libxrandr2 \
  libxkbcommon0 libxfixes3 libxcomposite1 libxdamage1 libpango-1.0-0 libcairo2 >/dev/null
sudo apt-get install -y -qq libasound2t64 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 >/dev/null \
  || sudo apt-get install -y -qq libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 >/dev/null
