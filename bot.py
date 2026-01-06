import os
import re
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ====== FUNCTIONS ======
def resolve_tiktok_short(url: str) -> str:
    try:
        r = requests.head(url, allow_redirects=True, timeout=5)
        return r.url
    except:
        return url

async def extract_caption(url: str) -> str:
    # TikTok caption (basic) atau YouTube title
    if "tiktok.com" in url or "vt.tiktok.com" in url:
        # TikTok API basic
        return "🎵 Video TikTok"
    try:
        res = requests.get(url, timeout=5)
        title_match = re.search(r"<title>(.*?)</title>", res.text)
        return title_match.group(1) if title_match else "❌ Caption tidak ditemukan"
    except:
        return "❌ Caption tidak ditemukan"

def translate(text: str) -> str:
    try:
        return GoogleTranslator(source="auto", target="id").translate(text)
    except:
        return text

# ====== DOWNLOAD FUNCTIONS ======
# YouTube via SaveFrom
def download_youtube(url: str) -> str:
    try:
        if "youtu" not in url:
            return None
        vid_id = re.search(r"(?:v=|youtu\.be/)([\w-]+)", url).group(1)
        res = requests.get(f"https://ssyoutube.com/watch?v={vid_id}", timeout=10)
        match = re.search(r'href="(https://[^"]+\.mp4)"', res.text)
        if match:
            video_url = match.group(1)
            file_path = "video.mp4"
            with requests.get(video_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return file_path
        return None
    except:
        return None

# TikTok via TikMate API (gabung repo)
async def download_tiktok(url: str) -> str:
    url = resolve_tiktok_short(url)
    try:
        api_url = f"https://api.tikmate.app/api/lookup?url={url}"
        res = requests.get(api_url, timeout=10).json()
        video_url = res["video"]["url_no_watermark"]
        file_path = "video.mp4"
        with requests.get(video_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return file_path
    except:
        return None

# ====== HANDLERS ======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.startswith("http"):
        await update.message.reply_text("❌ Kirim link TikTok / YouTube")
        return

    context.user_data["last_url"] = text
    await update.message.reply_text("⚡ Mengambil caption...")

    caption = await extract_caption(text)
    translated = translate(caption)
    context.user_data["last_caption"] = translated

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Copy Caption", callback_data="copy")],
            [InlineKeyboardButton("⬇️ Download Video", callback_data="download")],
        ]
    )

    await update.message.reply_text(
        f"📝 CAPTION (ID):\n\n{translated[:3500]}",
        reply_markup=keyboard,
    )

async def copy_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    caption = context.user_data.get("last_caption", "❌ Tidak ada caption")
    await query.message.reply_text(caption[:4000])

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Downloading video...")

    url = context.user_data.get("last_url")
    if not url:
        await query.message.reply_text("❌ URL tidak ditemukan.")
        return

    try:
        if "tiktok.com" in url or "vt.tiktok.com" in url:
            file_path = await download_tiktok(url)
            if not file_path:
                await query.message.reply_text("❌ Gagal download TikTok, coba lagi nanti atau pakai link asli.")
                return
        else:
            file_path = download_youtube(url)
            if not file_path:
                await query.message.reply_text("❌ Gagal download YouTube, coba lagi.")
                return

        await query.message.reply_video(video=open(file_path, "rb"))
        os.remove(file_path)
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal download:\n{e}")

# ====== MAIN ======
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(copy_caption, pattern="copy"))
    app.add_handler(CallbackQueryHandler(download_handler, pattern="download"))

    print("🤖 Bot TikTok + YouTube (gabungan) GRATIS aktif...")
    app.run_polling()

if __name__ == "__main__":
    main()
