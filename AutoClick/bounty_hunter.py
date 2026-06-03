#!/usr/bin/env python3
"""
둠스데이 현상금 사냥 자동화
- 캠페인 → 현상금 사냥 → 시작 → 대기 → 팝업 취소 → 완료 감지 → 반복
"""

import pyautogui
import time
import os
import sys
import subprocess

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

# ── 좌표 설정 ──────────────────────────────────────────
CAMPAIGN_BTN = (866, 801)  # 캠페인 버튼
BOUNTY_BTN = (1174, 488)  # 현상금 사냥 버튼
START_BTN = (711, 672)  # 시작하기 버튼
BACK_BTN = (51, 133)  # 뒤로가기 버튼
CANCEL_BTN = (548, 636)  # 팝업 취소 버튼

# ── 이미지 경로 ────────────────────────────────────────
IMG_DIR = os.path.expanduser("~/AutoClicker/AutoClick")
CANCEL_IMG = os.path.join(IMG_DIR, "cancel_btn.png")
PROGRESS_IMG = os.path.join(IMG_DIR, "in_progress.png")

# ── 설정 ───────────────────────────────────────────────
CLICK_DELAY = 0.8  # 클릭 사이 간격 (초)
SCAN_INTERVAL = 2.0  # 이미지 감지 주기 (초)
CONFIDENCE = 0.8  # 이미지 일치 민감도 (0~1)


def click(pos, delay=CLICK_DELAY):
    pyautogui.click(pos[0], pos[1])
    print(f"  클릭: {pos}")
    time.sleep(delay)


def find_image(img_path, confidence=CONFIDENCE):
    """화면에서 이미지 찾기. 찾으면 위치 반환, 없으면 None"""
    try:
        loc = pyautogui.locateOnScreen(img_path, confidence=confidence)
        return loc
    except Exception:
        return None


def start_bounty():
    """현상금 사냥 시작 시퀀스"""
    print("\n🎯 현상금 사냥 시작 시퀀스...")

    subprocess.run(["osascript", "-e", 'tell application "BlueStacks" to activate'])

    time.sleep(1)

    click(CAMPAIGN_BTN)  # 캠페인
    click(BOUNTY_BTN)  # 현상금 사냥
    click(START_BTN)  # 시작하기
    click(BACK_BTN)  # 뒤로가기 1
    click(BACK_BTN)  # 뒤로가기 2

    print("✅ 대기열 등록 완료! 팝업 감지 대기 중...")


def wait_for_popup():
    """팝업이 뜰 때까지 대기 후 취소 클릭"""
    print("👀 매칭 팝업 감지 중...")
    while True:
        loc = find_image(CANCEL_IMG)
        if loc:
            print("🔔 팝업 감지! 취소 클릭")
            click(CANCEL_BTN, delay=1)
            return
        time.sleep(SCAN_INTERVAL)


def wait_for_finish():
    """'진행 중' 버튼이 사라질 때까지 대기"""
    print("⏳ 게임 진행 중... 완료 감지 대기 중...")

    # 먼저 진행 중 버튼이 나타날 때까지 잠깐 대기
    time.sleep(3)

    while True:
        loc = find_image(PROGRESS_IMG)
        if loc is None:
            print("✅ 게임 완료 감지!")
            return
        time.sleep(SCAN_INTERVAL)


def main():
    print("=" * 50)
    print("  둠스데이 현상금 사냥 자동화")
    print("  종료: Ctrl+C")
    print("=" * 50)
    print("\n5초 후 시작... 블루스택으로 전환하세요!")
    time.sleep(5)

    MAX_LOOPS = 10  # 최대 루프 횟수 (0은 무한 루프)
    loop = 0
    while loop < MAX_LOOPS:
        loop += 1
        print(f"\n{'='*50}")
        print(f"  {loop}/{MAX_LOOPS} 번째 루프 시작")
        print(f"{'='*50}")

        start_bounty()  # 1. 현상금 사냥 시작
        wait_for_popup()  # 2. 팝업 감지 → 취소
        wait_for_finish()  # 3. 게임 완료 감지

        print("🔄 다음 루프 준비 중... (3초 대기)")
        time.sleep(3)
    print(f"\n✅ {MAX_LOOPS}번 완료!")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹ 자동화 종료!")
