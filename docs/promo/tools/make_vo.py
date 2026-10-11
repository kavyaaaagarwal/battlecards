"""Battlecards film VO with ElevenLabs, one request per line, with character timestamps.

Lines are placed on the film's timeline with directed pauses; cue words (from the timestamps) become
anchors that warp the animation so each visual beat lands on its spoken word (anchors.json).
Responses are cached in OUT/lines/, so re-running only re-places audio and costs nothing.
Key: ELEVENLABS_API_KEY from /Users/ritik/Expo/radar/.env."""
import base64, json, os, pathlib, subprocess, sys, urllib.request

OUT = pathlib.Path(sys.argv[1])
VOICE = os.environ.get("VOICE_ID", "nPczCjzI2devNBz1zQrb")  # Brian: deep, resonant narrator
SETTINGS = {"stability": 0.38, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True, "speed": 0.95}

# text, [(cue word, design time)], pause after (s)
LINES = [
    ("Every deal is different.", [("Every", 0.15)], 0.55),
    ("Your battlecard isn't.", [("Your", 1.95)], 1.0),
    ("A CFO wants price. I.T. wants integrations. A renewal needs a defence.",
     [("A CFO", 3.9), ("I.T.", 5.35), ("A renewal", 6.8)], 0.6),
    ("Your rep gets one generic card, and makes up the rest.", [("Your", 8.7), ("makes", 10.0)], 1.0),
    ("Battlecards fixes that.", [("Battlecards", 12.95), ("fixes", 13.5)], 0.45),
    ("Name your rivals.", [("Name", 14.45)], 0.9),
    ("Weeks of scattered research. Reviews, forums, news, pricing pages, pulled together in about two minutes.",
     [("Weeks", 16.1), ("Reviews", 18.0), ("forums", 18.55), ("news", 19.05), ("pricing", 19.55), ("pulled", 20.35)], 0.75),
    ("Current. Cited. Structured by what wins deals.", [("Current", 22.6), ("Cited", 23.4), ("Structured", 24.2)], 1.0),
    ("Now tell it about your deal.", [("Now", 26.6)], 0.5),
    ("Size. Prospect. Stage. Buyer. Situation.",
     [("Size", 28.6), ("Prospect", 29.25), ("Stage", 29.95), ("Buyer", 30.65), ("Situation", 31.35)], 0.8),
    ("In seconds, the card rebuilds around it.", [("In", 32.05)], 0.9),
    ("A CFO negotiating? Pricing and objections lead.", [("A CFO", 35.05), ("Pricing", 36.2)], 0.85),
    ("I.T. in discovery? Integrations, and your sharpest questions.", [("I.T.", 39.05), ("Integrations", 40.2)], 0.9),
    ("Every point links to its proof.", [("Every", 43.6)], 1.0),
    ("Send the link, and your rep walks in with a card built for this deal.", [("Send", 46.6), ("and", 47.5)], 1.1),
    ("Battlecards.", [("Battlecards", 52.2)], 0.6),
    ("A card for every deal, not just every competitor.", [("A card", 53.3), ("not", 54.2)], 0.0),
]

def key():
    for line in pathlib.Path("/Users/ritik/Expo/radar/.env").read_text().splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ELEVENLABS_API_KEY not found")

(OUT / "lines").mkdir(parents=True, exist_ok=True)
api_key = None
for i, (text, _, _) in enumerate(LINES):
    js = OUT / "lines" / f"l{i:02d}.json"
    if js.exists():
        continue
    api_key = api_key or key()
    body = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": SETTINGS, "seed": 11,
            "previous_text": " ".join(l[0] for l in LINES[max(0, i - 2):i]) or None,
            "next_text": " ".join(l[0] for l in LINES[i + 1:i + 3]) or None}
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps(body).encode(), headers={"xi-api-key": api_key, "Content-Type": "application/json"})
    res = json.loads(urllib.request.urlopen(req, timeout=90).read())
    (OUT / "lines" / f"l{i:02d}.mp3").write_bytes(base64.b64decode(res["audio_base64"]))
    js.write_text(json.dumps(res["alignment"]))
    print("generated", i, text)

def first_voiced(al):  # mp3 has a little lead-in silence; the line "starts" at its first character
    return al["character_start_times_seconds"][0]

anchors, cursor, placed = [], 0.0, []
for i, (text, cues, pause) in enumerate(LINES):
    al = json.loads((OUT / "lines" / f"l{i:02d}.json").read_text())
    chars = "".join(al["characters"])
    st, en = al["character_start_times_seconds"], al["character_end_times_seconds"]
    lead = first_voiced(al)
    rel = []
    pos = 0
    for word, design in cues:
        j = chars.index(word, pos); pos = j + len(word)
        rel.append((st[j] - lead, design))
    # start the line so its first cue lands on its design time, unless the previous line is still talking
    start = max(cues[0][1] - rel[0][0], cursor)
    placed.append((i, start - lead))
    for r, design in rel:
        anchors.append({"audio": round(start + r, 3), "design": design})
    end = start + (en[-1] - lead)
    anchors_line = {"start": round(start, 3), "end": round(end, 3)}
    LINES[i] = (text, cues, pause, anchors_line)
    cursor = end + pause * float(os.environ.get("PS", "1"))

total = round(cursor + 2.8, 3)
inputs, filt = [], []
for n, (i, at) in enumerate(placed):
    inputs += ["-i", str(OUT / "lines" / f"l{i:02d}.mp3")]
    filt.append(f"[{n}:a]aresample=48000,adelay={int(max(0, at) * 1000)}:all=1[a{n}]")
filt.append("".join(f"[a{n}]" for n in range(len(placed))) + f"amix=inputs={len(placed)}:normalize=0,apad,atrim=0:{total}[vo]")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[vo]",
                "-ac", "1", str(OUT / "vo_raw.wav")], check=True)

json.dump({"duration": total, "anchors": anchors,
           "lines": [{"text": l[0], **l[3]} for l in LINES]}, open(OUT / "anchors.json", "w"), indent=1)
print(f"duration {total:.2f}s; worst slip {max(a['audio'] - a['design'] for a in anchors):.2f}s")
for a in anchors:
    print(f"  design {a['design']:6.2f} -> audio {a['audio']:6.2f}")
