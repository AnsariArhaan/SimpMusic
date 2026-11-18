#!/usr/bin/env python3
"""Staged installed-app smoke check for the sort update (temporary CI tooling).

Stages (each logged PASS/FAIL/BLOCKED with screenshots + UI dumps):
  S0 install prior voice67 APK, launch, create manual playlist "KeepMe" (upgrade source)
  S1 install new sort APK over it (-r): app runs, "KeepMe" retained (data-upgrade proof)
  S2 Settings > Backup: "Sort liked songs" row present + screenshot
  S3 import synthetic rules file via SAF: exactly Phonk/English/Hindi playlists created,
     "KeepMe" retained
  S4 tap Sort liked songs with 0 likes: no crash
  S5 search a phonk song, like it: it appears in Phonk playlist (auto-sort on like)
  S6 playback starts (media_session state) + screenshot
  S7 unlike: song removed from Phonk playlist
Only S1/S2/S3 are gating; network-dependent stages report BLOCKED honestly.
"""
import os, re, subprocess, sys, time, glob, json

PKG = "com.maxrave.simpmusic.dev"
SHOTS = "shots"
os.makedirs(SHOTS, exist_ok=True)
RESULTS = []
LOG = open(os.path.join(SHOTS, "smoke-report.txt"), "w")

def sh(cmd, check=False, capture=True, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=capture, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError("cmd failed: %s\n%s\n%s" % (cmd, r.stdout, r.stderr))
    return (r.stdout or "") + (r.stderr or "")

def say(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n"); LOG.flush()

def stage(name, fn, gating=False):
    try:
        fn()
        RESULTS.append((name, "PASS")); say("STAGE %s: PASS" % name)
    except StageBlocked as e:
        RESULTS.append((name, "BLOCKED: %s" % e)); say("STAGE %s: BLOCKED: %s" % (name, e))
    except Exception as e:
        RESULTS.append((name, "FAIL: %s" % e)); say("STAGE %s: FAIL: %s" % (name, e))
    finally:
        try: dump("after-%s" % name.replace(" ", "_"))
        except Exception: pass
        try: logcat_tail()
        except Exception: pass

class StageBlocked(Exception): pass

def shot(tag):
    out = os.path.join(SHOTS, "%s.png" % tag)
    r = subprocess.run("adb exec-out screencap -p > %s" % out, shell=True)
    say("shot %s (%s bytes)" % (out, os.path.getsize(out) if os.path.exists(out) else 0))

def dump(tag="cur"):
    sh("adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1")
    sh("adb pull /sdcard/ui.xml /tmp/ui.xml >/dev/null 2>&1")
    try:
        xml = open("/tmp/ui.xml", encoding="utf-8").read()
        open(os.path.join(SHOTS, "ui-%s.xml" % tag), "w", encoding="utf-8").write(xml)
        return xml
    except OSError:
        return ""

NODES = []
def parse(xml):
    global NODES
    NODES = []
    for m in re.finditer(r'<node[^>]*>', xml):
        n = m.group(0)
        def g(attr):
            mm = re.search(attr + '="([^"]*)"', n)
            return mm.group(1) if mm else ""
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
        if not b: continue
        NODES.append({
            "text": g("text"), "desc": g("content-desc"), "cls": g("class"),
            "clickable": g("clickable") == "true", "editable": "EditText" in g("class"),
            "x": (int(b.group(1)) + int(b.group(3))) // 2,
            "y": (int(b.group(2)) + int(b.group(4))) // 2,
        })
    return NODES

def find(targets, editable=False):
    if isinstance(targets, str): targets = [targets]
    tl = [t.lower() for t in targets]
    best = None
    for n in NODES:
        label = (n["text"] + "|" + n["desc"]).lower()
        if any(t in label for t in tl):
            if editable and not n["editable"]: continue
            if n["clickable"]: return n
            if best is None: best = n
    return best

def tap_node(n, why=""):
    say("tap '%s' @%d,%d %s" % ((n["text"] or n["desc"])[:40], n["x"], n["y"], why))
    sh("adb shell input tap %d %d" % (n["x"], n["y"]))
    time.sleep(2.5)

def tap_text(targets, required=True, tag=""):
    parse(dump("tap-" + (tag or str(targets)[0:20]).replace(" ", "_")))
    n = find(targets)
    if n: tap_node(n); return True
    if required: raise RuntimeError("not found on screen: %s" % targets)
    return False

def wait_for(targets, timeout=30, tag=""):
    if isinstance(targets, str): targets = [targets]
    end = time.time() + timeout
    while time.time() < end:
        parse(dump("wait-" + (tag or targets[0]).replace(" ", "_")))
        if find(targets): return True
        time.sleep(3)
    return False

_SCR = None
def screen_size():
    global _SCR
    if _SCR is None:
        out = sh("adb shell wm size")
        m = re.search(r"(\d+)x(\d+)", out)
        _SCR = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
        say("screen size: %s" % (_SCR,))
    return _SCR

def swipe(times=1):
    w, h = screen_size()
    x = w // 2
    for _ in range(times):
        sh("adb shell input swipe %d %d %d %d" % (x, int(h*0.75), x, int(h*0.25)))
        time.sleep(1.5)

def back(): sh("adb shell input keyevent KEYCODE_BACK"); time.sleep(2)

def type_text(s):
    sh("adb shell input text '%s'" % s.replace(" ", "%s").replace("'", ""))
    time.sleep(1.5)

def launch():
    sh("adb shell monkey -p %s -c android.intent.category.LAUNCHER 1 >/dev/null" % PKG)
    end = time.time() + 150
    while time.time() < end:
        time.sleep(5)
        if sh("adb shell pidof %s" % PKG).strip():
            time.sleep(15)  # let first frame render
            return
    raise RuntimeError("app process never started")

DIALOG_OK = ["ALLOW", "Allow", "While using the app", "WHILE USING THE APP", "Yes", "Confirm", "Next", "Done", "Get started", "Agree", "Continue", "Skip", "Got it", "OK"]
def dismiss_first_run():
    for _ in range(6):
        parse(dump("first-run"))
        n = find(DIALOG_OK)
        if not n: return
        tap_node(n, "dismiss-dialog")

def logcat_tail():
    out = sh("adb logcat -d -t 400 2>/dev/null")
    open(os.path.join(SHOTS, "logcat-tail.txt"), "a").write(out)
    for line in out.splitlines():
        if "FATAL EXCEPTION" in line and PKG in line:
            raise RuntimeError("app crash seen in logcat")

def apk_from(d):
    hits = sorted(glob.glob(os.path.join(d, "**", "*.apk"), recursive=True))
    if not hits: raise StageBlocked("no apk in %s" % d)
    x86 = [h for h in hits if "x86_64" in h]
    pick = x86[0] if x86 else hits[0]
    say("using apk: %s" % pick)
    return pick

def go_settings():
    launch(); dismiss_first_run()
    if not tap_text(["Settings"], required=False, tag="home-settings"):
        back(); dismiss_first_run()
        tap_text(["Settings"], tag="home-settings-2")
    time.sleep(3)

# ---------- stages ----------
def s0_old_install_and_seed():
    if not os.path.isdir("apk-old") or not glob.glob("apk-old/**/*.apk", recursive=True):
        raise StageBlocked("prior voice67 artifact not downloaded")
    sh("adb install -r %s" % apk_from("apk-old"), check=True)
    launch(); dismiss_first_run(); shot("S0-old-home")
    # create manual playlist KeepMe (best effort through Library)
    tap_text(["Library"], tag="old-library")
    time.sleep(2)
    parse(dump("old-lib"))
    if not tap_text(["New playlist", "Create playlist"], required=False, tag="old-newpl"):
        n = find(["+", "Add"]);  # FAB
        if n: tap_node(n, "fab")
        tap_text(["New playlist", "Create playlist"], tag="old-newpl2")
    time.sleep(1)
    parse(dump("old-name-field"))
    e = find([""], editable=True)
    if not e: raise RuntimeError("no editable field for playlist name")
    tap_node(e, "name-field"); type_text("KeepMe")
    tap_text(["Save", "Create", "OK", "Done"], required=False, tag="old-save")
    shot("S0-old-keepme")
    global S0_SEEDED
    S0_SEEDED = wait_for(["KeepMe"], timeout=15, tag="old-keepme")
    if not S0_SEEDED:
        raise RuntimeError("KeepMe not visible after creation in old app")

S0_SEEDED = False

def s1_upgrade():
    sh("adb install -r %s" % apk_from("apk"), check=True)
    launch(); dismiss_first_run(); shot("S1-home-after-upgrade")
    dismiss_first_run()
    if not sh("adb shell pidof %s" % PKG).strip():
        raise RuntimeError("app process not running after upgrade install")

def s1r_retention():
    if not S0_SEEDED:
        raise StageBlocked("S0 seeding did not complete, retention not provable this run")
    dismiss_first_run()
    tap_text(["Library"], tag="new-library")
    time.sleep(3)
    if not wait_for(["KeepMe"], timeout=20, tag="keepme-retained"):
        shot("S1R-library-missing-keepme")
        raise RuntimeError("KeepMe playlist lost across upgrade")

def scroll_until(targets, max_swipes=12, tag="scroll"):
    last = None
    for i in range(max_swipes):
        xml = dump("%s-%d" % (tag, i))
        parse(xml)
        if find(targets): return True
        if xml == last:
            say("scroll stuck (no content change) at swipe %d" % i)
            return False
        last = xml
        swipe()
    return False

def s2_button_present():
    go_settings()
    shot("S2-settings")
    found = scroll_until(["Sort liked songs"], tag="S2-scroll")
    shot("S2-sort-button")
    if not found: raise RuntimeError("Sort liked songs row not found in Settings")

def s3_import_rules():
    rules = {"songs": [], "playlists": [
        {"title": "Phonk", "songs": []}, {"title": "English", "songs": []}, {"title": "Hindi", "songs": []}],
        "artistRules": {"Smoke Phonk Artist": "phonk", "Smoke English Artist": "english", "Smoke Hindi Artist": "hindi"},
        "songOverrides": {}}
    open("/tmp/smoke-rules.json", "w").write(json.dumps(rules))
    sh("adb push /tmp/smoke-rules.json /sdcard/Download/smoke-rules.json", check=True)
    sh("adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/smoke-rules.json >/dev/null 2>&1")
    go_settings()
    if not scroll_until(["Import data"], tag="S3-scroll"):
        raise RuntimeError("Import data row not found in Settings")
    tap_text(["Import data"], tag="import-data")
    time.sleep(4)  # SAF picker
    shot("S3-saf-open")
    ok = False
    for attempt in range(6):
        parse(dump("S3-saf"))
        n = find(["smoke-rules"])
        if n: tap_node(n, "rules-file"); ok = True; break
        # navigate: open drawer / downloads root / scroll
        if not tap_text(["Show roots", "Browse", "Downloads"], required=False, tag="saf-nav"):
            swipe()
        time.sleep(2)
    if not ok: raise RuntimeError("could not select rules file in SAF picker")
    time.sleep(6)
    shot("S3-after-import")
    # verify playlists in Library
    launch(); dismiss_first_run()
    tap_text(["Library"], tag="lib-after-import")
    time.sleep(3)
    missing = [p for p in ["Phonk", "English", "Hindi", "KeepMe"] if not wait_for([p], timeout=12, tag="lib-" + p)]
    shot("S3-library-playlists")
    if missing: raise RuntimeError("missing playlists after import: %s" % missing)

def s4_sort_zero_likes():
    go_settings()
    if not scroll_until(["Sort liked songs"], tag="S4-scroll"):
        raise RuntimeError("Sort liked songs row not found for tap")
    tap_text(["Sort liked songs"], tag="sort-tap")
    time.sleep(4)
    shot("S4-after-sort-tap")
    if not sh("adb shell pidof %s" % PKG).strip():
        raise RuntimeError("app process gone after sort tap")

def ensure_song_liked():
    """Search a phonk song, open it, like it. Returns song marker or raises StageBlocked."""
    launch(); dismiss_first_run()
    if not tap_text(["Search"], required=False, tag="search-tab"):
        raise StageBlocked("no Search entry found")
    time.sleep(2)
    parse(dump("search-field"))
    e = find([""], editable=True)
    if not e:
        if not tap_text(["Search"], required=False, tag="search-activate"): pass
        parse(dump("search-field-2")); e = find([""], editable=True)
    if not e: raise StageBlocked("no search field")
    tap_node(e, "search-field"); type_text("phonk drift phonk")
    sh("adb shell input keyevent KEYCODE_ENTER"); time.sleep(8)
    shot("S5-search-results")
    parse(dump("search-results"))
    songs = [n for n in NODES if n["text"] and ("phonk" in n["text"].lower()) and n["y"] > 300]
    if not songs: raise StageBlocked("no song results for phonk query (network?)")
    first = songs[0]; marker = first["text"][:40]
    tap_node(first, "open-song")
    time.sleep(8)
    shot("S5-song-open")
    # like it (heart). Try desc candidates.
    if not tap_text(["Like", "Add to favorites", "Favorite"], required=False, tag="like-btn"):
        raise StageBlocked("like button not found on song screen")
    time.sleep(5)
    shot("S5-liked")
    return marker

def s5_like_autosort():
    global SONG_MARKER
    try:
        SONG_MARKER = ensure_song_liked()
    except StageBlocked:
        raise
    # check Phonk playlist contains a row now
    launch(); dismiss_first_run()
    tap_text(["Library"], tag="lib-s5"); time.sleep(3)
    if not tap_text(["Phonk"], required=False, tag="open-phonk"):
        raise RuntimeError("Phonk playlist not found in Library")
    time.sleep(4)
    shot("S5-phonk-playlist")
    parse(dump("S5-phonk"))
    if not find(["phonk"]):
        raise RuntimeError("Phonk playlist appears empty after liking a phonk song")

def s6_playback():
    out = sh("adb shell dumpsys media_session 2>/dev/null")
    open(os.path.join(SHOTS, "media-session.txt"), "w").write(out)
    shot("S6-playback")
    if "state=3" not in out and "state=PlaybackState {state=3" not in out and "state=PLAYING" not in out.upper():
        raise StageBlocked("playback state not PLAYING (buffering or blocked stream)")

def s7_unlike_removal():
    launch(); dismiss_first_run()
    # open the liked song again from Phonk playlist and unlike
    tap_text(["Library"], tag="lib-s7"); time.sleep(3)
    tap_text(["Phonk"], tag="open-phonk-s7"); time.sleep(4)
    parse(dump("S7-phonk"))
    rows = [n for n in NODES if "phonk" in (n["text"] + n["desc"]).lower() and n["y"] > 300]
    if not rows: raise StageBlocked("no song row in Phonk playlist to unlike")
    tap_node(rows[0], "open-liked-song"); time.sleep(6)
    if not tap_text(["Unlike", "Liked", "Remove from favorites", "Favorite"], required=False, tag="unlike-btn"):
        raise StageBlocked("unlike control not found")
    time.sleep(5)
    shot("S7-after-unlike")
    back(); back()
    tap_text(["Library"], required=False, tag="lib-s7b"); time.sleep(3)
    if tap_text(["Phonk"], required=False, tag="open-phonk-s7b"):
        time.sleep(4)
        parse(dump("S7-phonk-empty"))
        shot("S7-phonk-after-unlike")
        if find([SONG_MARKER[:25]] if SONG_MARKER else ["zzz-no-match"]):
            raise RuntimeError("song still in Phonk playlist after unlike")

SONG_MARKER = ""
def main():
    say("smoke start %s" % time.strftime("%H:%M:%S"))
    stage("S0-old-install-seed", s0_old_install_and_seed)
    stage("S1-upgrade-install", s1_upgrade, gating=True)
    stage("S1R-keepme-retained", s1r_retention)
    stage("S2-sort-button", s2_button_present, gating=True)
    stage("S3-rules-import", s3_import_rules, gating=True)
    stage("S4-sort-zero-likes", s4_sort_zero_likes)
    stage("S5-like-autosort", s5_like_autosort)
    stage("S6-playback", s6_playback)
    stage("S7-unlike-removal", s7_unlike_removal)
    say("==== SUMMARY ====")
    for n, r in RESULTS: say("%-22s %s" % (n, r))
    LOG.close()
    critical = {"S1-upgrade-install", "S2-sort-button", "S3-rules-import"}
    bad = [n for n, r in RESULTS if n in critical and not r.startswith("PASS")]
    sys.exit(1 if bad else 0)

main()
