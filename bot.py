import os
import re
import time
import asyncio
import logging
import shutil
from pyrogram import Client, filters
import whisper
from pydub import AudioSegment

# --- ချိန်ညှိချက်များ (Configuration) ---
API_ID = 37289442
API_HASH = "66ce67a84ce9e8b9d49ef3d66acdaf1c"
BOT_TOKEN = "8943816710:AAGYJG5XLui1CccrBzpZtG9YdoRubxiJcfM"

BACKGROUND_COLOR = '#b0b0b0'
CORNER_RADIUS = 40
WORK_DIR = "bot_workspace"

if not os.path.exists(WORK_DIR):
    os.makedirs(WORK_DIR)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

app = Client("recap_smart_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Whisper Model (Block မဖြစ်စေရန် Thread ထဲတွင် run မည်)
whisper_model = whisper.load_model("tiny")

# State Management
user_data = {}

def cleanup_workspace(uid):
    folder_path = os.path.join(WORK_DIR, uid)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)

def format_time(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{mins:02}:{secs:02}.{ms:03}"

def parse_time(time_str):
    time_str = time_str.strip()
    ms = 0
    if '.' in time_str:
        main, ms_str = time_str.split('.')
        ms = int(ms_str.ljust(3, '0')[:3])
    else:
        main = time_str
    
    parts = main.split(':')
    mins = int(parts[0])
    secs = int(parts[1])
    return (mins * 60 * 1000) + (secs * 1000) + ms

async def run_cmd(*cmd):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await proc.communicate()
    return proc.returncode

async def run_shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await proc.communicate()
    return proc.returncode

def transcribe_audio(audio_path):
    return whisper_model.transcribe(audio_path)

def build_combined_audio(segments, speed, video_duration_ms, uid):
    folder_path = os.path.join(WORK_DIR, uid)
    combined_audio = AudioSegment.silent(duration=video_duration_ms)
    
    import subprocess
    
    for start_ms, text in segments:
        temp_tts = os.path.join(folder_path, f"tts_{start_ms}.mp3")
        tts_cmd = f'edge-tts --voice my-MM-ThihaNeural --rate {speed} --text "{text.strip()}" --write-media "{temp_tts}"'
        
        subprocess.run(tts_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(temp_tts):
            seg_audio = AudioSegment.from_file(temp_tts)
            combined_audio = combined_audio.overlay(seg_audio, position=start_ms)
            os.remove(temp_tts)
            
    final_audio_path = os.path.join(folder_path, "final_audio.wav")
    combined_audio.export(final_audio_path, format="wav")
    return final_audio_path

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    chat_id = message.chat.id
    if chat_id in user_data:
        cleanup_workspace(user_data[chat_id].get('uid', ''))
    
    user_data[chat_id] = {'state': 'idle'}
    await message.reply_text("🌟 *Recap Smart Bot*\n\nဗီဒီယို (20MB အထက်လည်း ရပါသည်) ကို တိုက်ရိုက် ပို့ပေးပါဗျာ။")

@app.on_message(filters.video & filters.private)
async def handle_video(client, message):
    chat_id = message.chat.id
    
    uid = f"{chat_id}_{message.id}"
    folder_path = os.path.join(WORK_DIR, uid)
    os.makedirs(folder_path, exist_ok=True)
    
    if chat_id in user_data and 'uid' in user_data[chat_id]:
        cleanup_workspace(user_data[chat_id]['uid'])
        
    user_data[chat_id] = {'state': 'processing_video', 'uid': uid}
    
    status_msg = await message.reply_text("⏳ ဗီဒီယိုကို ဒေါင်းလုဒ်ဆွဲနေပါသည်... အနည်းငယ် စောင့်ပေးပါ။")
    
    try:
        video_path = os.path.join(folder_path, "input.mp4")
        await message.download(file_name=video_path)
        user_data[chat_id]['video_path'] = video_path
        
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        user_data[chat_id]['video_duration'] = float(stdout.decode().strip())
        
        await status_msg.edit_text("⏳ ဗီဒီယိုမှ အသံနှင့် စာသား (Script) များကို ထုတ်ယူနေပါသည်...")
        
        audio_path = os.path.join(folder_path, "temp_audio.wav")
        await run_cmd('ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', '-y', audio_path)
        
        result = await asyncio.to_thread(transcribe_audio, audio_path)
        
        script_text = "( သဘာ၀ကျကျ time အလိုက် ဘာသာပြ‌န်ပေး)\n\n"
        for seg in result['segments']:
            start = format_time(seg['start'])
            end = format_time(seg['end'])
            script_text += f"[{start}] - [{end}]\n{seg['text'].strip()}\n\n"
        
        if len(script_text) > 4000:
            for i in range(0, len(script_text), 4000):
                await message.reply_text(script_text[i:i+4000])
        else:
            await message.reply_text(script_text)

        await message.reply_text("🤖 အပေါ်က စာကို Copy ကူးပြီး ChatGPT မှာ ဘာသာပြန်စာ ပြန်ပို့ပေးပါလို့ ပြောလိုက်ပါ။ ပြီးရင် ChatGPT ပြန်ပေးတဲ့ မြန်မာစာ (Time တွေပါတဲ့အတိုင်း) ကို ဒီကို ပြန်ပို့ပေးပါ။")
        
        user_data[chat_id]['state'] = 'wait_translation'
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error ဖြစ်သွားပါသည်: {e}")
        cleanup_workspace(uid)

@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def handle_text(client, message):
    chat_id = message.chat.id
    data = user_data.get(chat_id, {})
    state = data.get('state', 'idle')
    user_text = message.text.strip()
    uid = data.get('uid', '')

    if state == 'wait_translation':
        lines = user_text.split('\n')
        processed_segments = []
        
        current_start = None
        current_end = None
        current_text = []
        
        # Bracket နှစ်ခုကြားက ဂဏန်းတွေကိုပဲ ဖမ်းယူမည့် ပုံစံ
        time_pattern = r'\[\s*([0-9:\.]+)\s*\].*?\[\s*([0-9:\.]+)\s*\]'
        
        for line in lines:
            line = line.strip()
            if not line:
                continue # စာကြောင်းအလွတ်များကို ကျော်သွားမည်
            
            match = re.search(time_pattern, line)
            if match:
                # အရင် Segment ရှိနေခဲ့လျှင် သိမ်းဆည်းမည်
                if current_start and current_text:
                    try:
                        processed_segments.append((parse_time(current_start), "\n".join(current_text)))
                    except Exception:
                        pass
                
                # Segment အသစ်စတင်မည်
                current_start = match.group(1)
                current_end = match.group(2)
                current_text = []
                
                # Time နောက်မှာ စာသားကပ်ပါလာခဲ့ရင် ဖမ်းယူမည်
                after_match = line[match.end():].strip()
                if after_match:
                    current_text.append(after_match)
            else:
                if current_start:
                    current_text.append(line)
        
        # နောက်ဆုံးကျန်နေခဲ့သော Segment ကို သိမ်းဆည်းမည်
        if current_start and current_text:
            try:
                processed_segments.append((parse_time(current_start), "\n".join(current_text)))
            except Exception:
                pass
                
        if not processed_segments:
            await message.reply_text("❌ Time format ဖတ်လို့မရပါ။ [00:00.000] - [00:05.000] ပုံစံ ပါဝင်ရပါမည်။ သေချာစစ်ဆေးပြီး ပြန်ပို့ပေးပါ။")
            return
            
        data['translated_segments'] = processed_segments
        data['state'] = 'wait_voice_speed'
        await message.reply_text("🗣 အသံထွက်မည့် အမြန်နှုန်း (Voice Speed) ကို သတ်မှတ်ပေးပါ။\n(ဥပမာ - +0%, +10%, -10% စသဖြင့် ရိုက်ထည့်ပါ)")

    elif state == 'wait_voice_speed':
        speed = user_text if '%' in user_text else f"+{user_text}%" if user_text.isdigit() else "+0%"
        data['voice_speed'] = speed
        data['state'] = 'processing_audio'
        
        status_msg = await message.reply_text("⏳ ယောကျာ်းလေးအသံ (သီဟ) ဖြင့် အသံဖန်တီးနေပြီး ဗီဒီယို Time နှင့် ညှိနေပါသည်...")
        
        video_duration_ms = int(data['video_duration'] * 1000)
        
        try:
            final_audio_path = await asyncio.to_thread(
                build_combined_audio, data['translated_segments'], speed, video_duration_ms, uid
            )
            
            data['final_audio_path'] = final_audio_path
            
            folder_path = os.path.join(WORK_DIR, uid)
            video_path = data['video_path']
            sample_video_path = os.path.join(folder_path, "sample.mp4")
            
            await status_msg.edit_text("⏳ 10-Second Sample ဗီဒီယို အစမ်းထုတ်လုပ်နေပါသည်...")
            
            await run_cmd(
                'ffmpeg', '-i', video_path, '-i', final_audio_path,
                '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'ultrafast',
                '-c:a', 'aac', '-t', '10', '-y', sample_video_path
            )
            
            await message.reply_video(video=sample_video_path, caption="🎬 အသံပေါင်းထည့်ထားသော 10 စက္ကန့်စာ Preview ပါ။\n\n📐 ဆက်လက်လုပ်ဆောင်ရန် ဗီဒီယို၏ အကျယ် (Width) ကို ဂဏန်းဖြင့် ရိုက်ပို့ပါ (ဥပမာ - 640):")
            
            data['state'] = 'wait_width'
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Audio ဖန်တီးရာတွင် Error ဖြစ်သွားပါသည်: {e}")
            cleanup_workspace(uid)

    elif state == 'wait_width':
        if not user_text.isdigit():
            await message.reply_text("❌ ဂဏန်းသီးသန့်ပဲ ရိုက်ပို့ပေးပါ။")
            return
        data['width'] = int(user_text)
        data['state'] = 'wait_height'
        await message.reply_text("📐 ဗီဒီယို၏ အမြင့် (Height) ကို ရိုက်ပို့ပါ (ဥပမာ - 450 သို့မဟုတ် 640):")

    elif state == 'wait_height':
        if not user_text.isdigit():
            await message.reply_text("❌ ဂဏန်းသီးသန့်ပဲ ရိုက်ပို့ပေးပါ။")
            return
        
        width = data['width']
        height = int(user_text)
        data['state'] = 'idle'
        
        folder_path = os.path.join(WORK_DIR, uid)
        video_path = data['video_path']
        final_audio_path = data['final_audio_path']
        final_output_path = os.path.join(folder_path, "final_output.mp4")
        
        status_msg = await message.reply_text("🚀 နောက်ဆုံး ဗီဒီယိုအပြည့်အစုံကို စတင် Render လုပ်နေပါပြီ...")
        
        crop_filter = f"crop='min(iw,ih*({width}/{height}))':'min(ih,iw*({height}/{width}))'"
        filter_complex = (
            f"color=c={BACKGROUND_COLOR}:s=720x1280[bg];"
            f"[0:v]{crop_filter},scale={width}:{height}[cropped];"
            f"[cropped]format=yuva420p,geq=lum='p(X,Y)':a='if(gt(abs(W/2-X),W/2-{CORNER_RADIUS})*gt(abs(H/2-Y),H/2-{CORNER_RADIUS}),if(lte(pow({CORNER_RADIUS}-(W/2-abs(W/2-X)),2)+pow({CORNER_RADIUS}-(H/2-abs(H/2-Y)),2),pow({CORNER_RADIUS},2)),255,0),255)'[rounded];"
            f"[bg][rounded]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]"
        )

        try:
            await run_cmd(
                'ffmpeg', '-i', video_path, '-i', final_audio_path,
                '-filter_complex', filter_complex,
                '-map', '[v]', '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac', '-y', final_output_path
            )
            
            await status_msg.edit_text("✅ ဗီဒီယို Render လုပ်ခြင်း ပြီးဆုံးပါပြီ။ Telegram သို့ Upload ပြုလုပ်နေပါသည်...")
            await message.reply_video(video=final_output_path, caption="🎉 အသံအသစ်နှင့် Edit လုပ်ထားသော ဗီဒီယို အပြည့်အစုံ ရပါပြီ။")
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Render လုပ်ရာတွင် Error ဖြစ်သွားပါသည်: {e}")
        finally:
            cleanup_workspace(uid)

if __name__ == '__main__':
    print("Recap Pyrogram Bot is running...")
    app.run()
