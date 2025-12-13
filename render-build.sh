#!/usr/bin/env bash

apt-get update
apt-get install -y chromium-browser chromium-chromedriver

echo "Chromium instalado em:"
which chromium-browser

echo "Chromedriver instalado em:"
which chromedriver
