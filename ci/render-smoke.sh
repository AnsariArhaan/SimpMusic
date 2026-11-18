#!/usr/bin/env bash
# TEMPORARY smoke check for the sort update: install the signed APK on an x86_64
# emulator, launch it, navigate Settings > Backup, and screenshot the sort button.
# No app dependencies changed, no user data involved; screenshots are UI pixels only.
set -uo pipefail
APK=$(find apk -name '*x86_64*.apk' | head -1)
[ -n "$APK" ] || { echo 'no x86_64 APK found'; exit 1; }
echo "== installing $APK"
adb install -r "$APK"
echo "== launching"
adb shell monkey -p com.maxrave.simpmusic.dev -c android.intent.category.LAUNCHER 1 >/dev/null
sleep 35
mkdir -p shots
shot() { adb exec-out screencap -p > "shots/$1.png" && echo "saved shots/$1.png ($(stat -c%s "shots/$1.png") bytes)"; }
dump() { adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb pull /sdcard/ui.xml /tmp/ui.xml >/dev/null 2>&1; }
tap_text() {
  dump || return 1
  python3 - "$1" <<'PY'
import sys, re, subprocess
target = sys.argv[1].lower()
try:
    xml = open('/tmp/ui.xml', encoding='utf-8').read()
except OSError:
    sys.exit(1)
for m in re.finditer(r'<node[^>]*>', xml):
    node = m.group(0)
    t = re.search(r'text="([^"]*)"', node)
    d = re.search(r'content-desc="([^"]*)"', node)
    label = ((t.group(1) if t else '') + '|' + (d.group(1) if d else '')).lower()
    if target in label:
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
        if b:
            x = (int(b.group(1)) + int(b.group(3))) // 2
            y = (int(b.group(2)) + int(b.group(4))) // 2
            subprocess.run(['adb', 'shell', 'input', 'tap', str(x), str(y)], check=False)
            print('tapped "%s" at %d,%d' % (target, x, y))
            sys.exit(0)
print('not found:', target)
sys.exit(1)
PY
}
shot 01-home
# Best effort: get to Settings (dismiss any first-run sheets first)
for attempt in 1 2 3; do
  tap_text 'Settings' && break
  tap_text 'Confirm' || tap_text 'Next' || tap_text 'Done' || tap_text 'Get started' || true
  sleep 4
done
sleep 4
shot 02-settings
# Scroll to the Backup group and find the sort row
FOUND=0
for i in 1 2 3 4 5 6 7 8; do
  dump
  if grep -qi 'sort liked songs' /tmp/ui.xml 2>/dev/null; then FOUND=1; break; fi
  adb shell input swipe 540 1800 540 500
  sleep 2
done
shot 03-sort-button
if [ "$FOUND" = 1 ]; then
  echo 'BUTTON VISIBLE IN UI TREE'
  tap_text 'sort liked songs' || true
  sleep 6
  shot 04-after-tap
else
  echo 'BUTTON NOT FOUND IN UI TREE'
  exit 1
fi
echo '== smoke check done'
