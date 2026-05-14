#!/bin/bash
# AutoClicker 실행 스크립트

echo "📦 필요한 패키지 설치 중..."
pip3 install pyautogui pynput --break-system-packages -q

echo "🚀 AutoClicker 실행!"
python3 "$(dirname "$0")/autoclicker.py"
