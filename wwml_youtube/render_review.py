
"""Render a narrated, inspectable WWML review cut using original graphics.
No publication and no provider credentials. Dependencies: Pillow, piper-tts, ffmpeg.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import wave
import shutil

from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice, SynthesisConfig
from .adapter import run_tool

W, H, FPS = 1280, 720, 24
GOLD = "#D8B66A"
WHITE = "#F5F4EF"
MUTED = "#A6B4C3"
BLUE = "#426EAA"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def command(args):
    subprocess.run([str(a) for a in args], check=True)

def ffprobe(path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path)], text=True))

def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)

def wrap(draw, text, face, width):
    lines, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=face) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines

def text_lines(draw, text, xy, face, width, colour=WHITE, spacing=1.25):
    lines = wrap(draw, text, face, width)
    for i, line in enumerate(lines):
        draw.text((xy[0], xy[1] + i * int(face.size * spacing)), line,
                  font=face, fill=colour)
    return len(lines) * int(face.size * spacing)

def base():
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    for y in range(H):
        ratio = y / H
        draw.line((0,y,W,y), fill=(int(11+7*ratio),int(20+9*ratio),int(34+13*ratio)))
    draw.polygon([(840,0),(1280,0),(1280,530),(630,530)], fill="#10233A")
    for x in range(60, W, 80):
        draw.line((x,95,x,520),fill="#1B2B3C",width=1)
    draw.line((60,94,1220,94),fill="#31465A",width=1)
    draw.text((60,38),"WEALTHY WELLNESS",font=font(22,True),fill=GOLD)
    draw.text((1060,43),"2027 SERIES",font=font(15),fill=MUTED)
    return image

def illustration(draw, section, progress):
    # A changing route motif connects each concrete action to its two intended goals.
    x, y = 850, 250
    draw.arc((810,150,1210,550),200,520,fill="#273E58",width=3)
    draw.arc((810,150,1210,550),200,200+max(2,int(320*progress)),fill=GOLD,width=5)
    draw.rounded_rectangle((790,215,1190,430),radius=24,fill="#152A42",outline="#34516E",width=2)
    big = section["big"]
    size = 68 if len(big) < 5 else 58
    face=font(size,True)
    draw.text((990-draw.textlength(big,font=face)/2,245),big,font=face,fill=GOLD)
    text_lines(draw,section["unit"],(825,337),font(20),330,MUTED)
    draw.text((812,467),"MONEY",font=font(18,True),fill=WHITE)
    draw.text((1068,467),"HEALTH",font=font(18,True),fill=WHITE)
    draw.line((894,480,1045,480),fill=BLUE,width=3)
    draw.ellipse((967,472,983,488),fill=GOLD)

def panel(section, caption, progress, section_index):
    image=base()
    draw=ImageDraw.Draw(image)
    draw.text((60,123),section["label"],font=font(21,True),fill=GOLD)
    text_lines(draw,section["heading"],(58,175),font(48,True),680)
    draw.rounded_rectangle((60,330,715,450),radius=14,fill="#172A3C")
    text_lines(draw,section["action"],(80,351),font(26),615,WHITE)
    draw.text((60,510),section["source"],font=font(15),fill=MUTED)
    illustration(draw,section,progress)
    # Sentence cues use exact synthesized WAV boundaries, not estimated timestamps.
    draw.rounded_rectangle((45,565,1235,699),radius=16,fill="#07111E")
    lines=wrap(draw,caption,font(27),1110)
    if len(lines)>3:
        raise ValueError("Caption exceeds three-line safe area: "+caption)
    cy=629-len(lines)*34/2
    for n,line in enumerate(lines):
        draw.text((640-draw.textlength(line,font=font(27))/2,cy+n*34),
                  line,font=font(27),fill=WHITE)
    draw.rectangle((60,543,1220,547),fill="#273A50")
    draw.rectangle((60,543,60+1160*progress,547),fill=GOLD)
    return image

def timestamp(t):
    millis=round(t*1000)
    h,rest=divmod(millis,3600000)
    m,rest=divmod(rest,60000)
    s,ms=divmod(rest,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def silence_samples(seconds, sample_rate):
    return b"\\x00\\x00" * round(seconds*sample_rate)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--model",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    project=json.loads(Path(args.project).read_text())
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    work=out/"work"
    work.mkdir(exist_ok=True)
    hookfile=work/"hooks.txt"
    hookfile.write_text("\n".join(project["hooks"]),encoding="utf-8")
    titlefile=work/"titles.txt"
    titlefile.write_text("\n".join(project["title_candidates"]),encoding="utf-8")
    hooks=run_tool("hook",[str(hookfile)])
    titles=run_tool("package",[str(titlefile),"--thumb",project["thumbnail_text"]])
    selected_hook=hooks["report"][0]["hook"]
    project["sections"][0]["sentences"][0]=selected_hook
    editorial={"hooks":hooks,"titles":titles,"selected_hook":selected_hook,
               "selected_title":project["title"],"review_status":"pending_review"}
    (out/"editorial_review.json").write_text(json.dumps(editorial,indent=2))
    voice=PiperVoice.load(args.model)
    config=SynthesisConfig(speaker_id=0,length_scale=1.10)
    cues=[]
    chapters=[]
    concat=[]
    pcm_parts=[]
    cursor=0.0
    idx=0
    sample_rate=None
    screenshots=[]
    for si,section in enumerate(project["sections"]):
        chapters.append({"start":cursor,"title":section["heading"]})
        script=section["sentences"]
        for qi,sentence in enumerate(script):
            wav_path=work/f"cue_{idx:03}.wav"
            with wave.open(str(wav_path),"wb") as wav:
                voice.synthesize_wav(sentence,wav,syn_config=config)
            with wave.open(str(wav_path),"rb") as wav:
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2:
                    raise ValueError("Expected mono PCM16 narration")
                if sample_rate is not None and sample_rate!=wav.getframerate():
                    raise ValueError("Inconsistent sample rates")
                sample_rate=wav.getframerate()
                pcm=wav.readframes(wav.getnframes())
            speech_duration=len(pcm)/2/sample_rate
            pause=0.45 if qi==len(script)-1 else 0.16
            # Pad each WAV to a whole frame so mux, captions and chapter boundaries agree.
            duration=math.ceil((speech_duration+pause)*FPS)/FPS
            padding=b"\x00\x00"*max(0,round(duration*sample_rate)-len(pcm)//2)
            pcm+=padding
            duration=len(pcm)/2/sample_rate
            with wave.open(str(wav_path),"wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(pcm)
            pcm_parts.append(pcm)
            cue={"index":idx+1,"start":cursor,"end":cursor+speech_duration,
                 "section":si,"text":sentence,"clip_duration":duration}
            cues.append(cue)
            progress=(qi+1)/len(script)
            image=panel(section,sentence,progress,si)
            img_path=work/f"frame_{idx:03}.png"
            image.save(img_path)
            if qi==0:
                screenshots.append(image.copy())
            clip=work/f"clip_{idx:03}.mp4"
            # Small camera drift on original artwork; captions stay within safe margins.
            command(["ffmpeg","-hide_banner","-loglevel","error","-y",
                "-loop","1","-framerate",str(FPS),"-i",img_path,"-i",wav_path,
                "-t",f"{duration:.6f}","-vf",
                "zoompan=z='min(zoom+0.000025,1.008)':d=1:s=1280x720:fps=24,format=yuv420p",
                "-c:v","libx264","-preset","ultrafast","-crf","20","-threads","2",
                "-c:a","aac","-b:a","160k","-ar","48000","-movflags","+faststart",clip])
            concat.append("file '"+str(clip.resolve())+"'")
            cursor+=duration
            idx+=1
            print(f"Rendered cue {idx}: {duration:.2f}s; timeline {cursor:.2f}s",flush=True)
    (out/"timeline.json").write_text(json.dumps(
        {"duration":cursor,"cues":cues,"chapters":chapters},indent=2))
    srt="\n\n".join(f"{c['index']}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}"
                    for c in cues)+"\n"
    (out/"subtitles.srt").write_text(srt,encoding="utf-8")
    with wave.open(str(out/"narration.wav"),"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(sample_rate)
        for pcm in pcm_parts:
            wav.writeframes(pcm)
    concatfile=work/"concat.txt"
    concatfile.write_text("\n".join(concat))
    video_only=work/"visuals.mp4"
    command(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
             "-i",concatfile,"-map","0:v:0","-c:v","copy",video_only])
    video=out/"video_review.mp4"
    command(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",video_only,
             "-i",out/"narration.wav","-i",out/"subtitles.srt",
             "-map","0:v:0","-map","1:a:0","-map","2:s:0","-c:v","copy",
             "-af","loudnorm=I=-16:TP=-1.5:LRA=11","-c:a","aac","-b:a","192k",
             "-c:s","mov_text","-metadata:s:s:0","language=eng",
             "-movflags","+faststart",video])
    probe=ffprobe(video)
    streams=probe["streams"]
    vs=next(s for s in streams if s["codec_type"]=="video")
    aus=next(s for s in streams if s["codec_type"]=="audio")
    vd=float(vs.get("duration",probe["format"]["duration"]))
    ad=float(aus.get("duration",probe["format"]["duration"]))
    assert vs["width"]==W and vs["height"]==H
    assert vs["codec_name"]=="h264"
    assert abs(vd-ad)<0.20,(vd,ad)
    assert abs(vd-cursor)<0.20,(vd,cursor)
    assert all(c["start"]<c["end"]<=cursor for c in cues)
    assert all(cues[i]["end"]<=cues[i+1]["start"] for i in range(len(cues)-1))
    command(["ffmpeg","-hide_banner","-loglevel","error","-i",video,"-f","null","-"])
    verification={"technical_status":"passed","visual_review":"pending","listening_review":"pending",
        "resolution":[W,H],"fps":FPS,"duration_seconds":vd,"audio_duration_seconds":ad,
        "cue_count":len(cues),"audio_video_delta_seconds":abs(vd-ad),
        "voice":project["voice"],"ffprobe":probe}
    (out/"render_verification.json").write_text(json.dumps(verification,indent=2))
    # Exact typography thumbnail draft; Canva production remains pending.
    thumb=base()
    d=ImageDraw.Draw(thumb)
    d.text((70,145),"DOUBLE",font=font(105,True),fill=WHITE)
    d.text((70,270),"RETURN",font=font(105,True),fill=GOLD)
    d.text((75,450),"7 HABITS  /  2027",font=font(33,True),fill=MUTED)
    d.ellipse((900,170,1160,430),outline=GOLD,width=8)
    d.text((968,220),"7",font=font(112,True),fill=WHITE)
    thumb.save(out/"thumbnail_draft.png")
    sheet=Image.new("RGB",(960,540),"#0C1726")
    for i,im in enumerate(screenshots[:9]):
        im.thumbnail((320,180))
        sheet.paste(im,((i%3)*320,(i//3)*180))
    sheet.save(out/"contact_sheet.jpg",quality=90)
    script_md="# "+project["title"]+"\n\n"
    for section in project["sections"]:
        script_md+="## "+section["heading"]+"\n\n"
        script_md+="[ON SCREEN: "+section["action"]+"]\n\n"
        script_md+=" ".join(section["sentences"])+"\n\n"
    (out/"script.md").write_text(script_md,encoding="utf-8")
    def chapter_label(t):
        whole=int(t)
        return f"{whole//60:02}:{whole%60:02}"
    desc=(
        "Seven practical habits that could support better health and stronger finances in 2027.\n"
        "Explore sleep, movement, meal planning, saving, spending pauses, skill practice and a weekly review.\n\n"
        +"\n".join(chapter_label(c["start"])+" "+c["title"] for c in chapters)
        +"\n\nEducational content. Results vary. Savings examples are illustrative CAD amounts, not promises.\n\n"
        +"Sources:\n"+"\n".join(s["url"] for s in project["sources"])
        +"\n\nReview-cut narration: Piper LibriTTS-R medium, speaker 0. Arthur narration pending.\n"
        "LibriTTS-R dataset and voice attribution: https://www.openslr.org/141/ (CC BY 4.0).\n"
        "Original graphics and editing: Wealthy Wellness / WWML.\n"
    )
    (out/"description.txt").write_text(desc,encoding="utf-8")
    manifest={"title":project["title"],"description_file":"description.txt",
        "tags":["Wealthy Wellness","2027 habits","healthy habits","money habits",
                "emergency savings","sleep habits","meal planning","personal finance"],
        "video":"video_review.mp4","thumbnail":"thumbnail_draft.png","captions":"subtitles.srt",
        "status":"review_cut","publish":False,
        "gates":{"technical":"passed","visual":"pending","listening":"pending",
                 "Arthur_narration":"pending","Canva_thumbnail":"pending","publishing":"not_requested"}}
    (out/"publish_manifest.json").write_text(json.dumps(manifest,indent=2))
    shutil.copyfile(args.project,out/"project_source.json")
    (out/"VOICE_CREDITS.txt").write_text(
        "Temporary review narration: Piper LibriTTS-R medium, speaker 0.\n"
        "Voice model: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/libritts_r/medium\n"
        "Dataset: LibriTTS-R https://www.openslr.org/141/ — CC BY 4.0.\n"
        "Synthesized and edited for this review cut. Not Arthur.\n")
    shutil.rmtree(work)
    print(json.dumps({"video":str(video),"duration":vd,"technical_status":"passed"}),flush=True)

if __name__=="__main__":
    main()
