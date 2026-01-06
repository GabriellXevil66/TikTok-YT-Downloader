import os
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from yt_dlp import YoutubeDL
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ===== YOUTUBE CONFIG =====
YDL_VIDEO_OPTS = {
    "format": "bestvideo[height<=720]+bestaudio/best",
    "outtmpl": "video.%(ext)s",
    "merge_output_format": "mp4",
    "quiet": True,
    "nocheckcertificate": True,
}

YDL_INFO_OPTS = {"quiet": True, "skip_download": True, "nocheckcertificate": True}

# ===== FUNCTIONS =====

async def extract_caption(url: str) -> str:
    # TikTok caption  (ambil judul halaman)
    if "tiktok.com" in url or "vt.tiktok.com" in url:
        return "🎵 TikTok Video"
    def run():
        with YoutubeDL(YDL_INFO_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("description") or info.get("title") or "❌ Tidak ada caption"
    return await asyncio.to_thread(run)

def translate(text: str) -> str:
    try:
        return GoogleTranslator(source="auto", target="id").translate(text)
    except:
        return text

async def download_youtube(url: str) -> str:
    def run():
        with YoutubeDL(YDL_VIDEO_OPTS) as ydl:
            info = ydl.extract_info(url)
            return ydl.prepare_filename(info)
    return await asyncio.to_thread(run)

async def download_tiktok(url: str) -> str:
    """
    Pakai TikWM API untuk TikTok tanpa watermark.
    Banyak bot di GitHub pakai ini.
    """
    try:
        # TikWM API endpoint
        api_url = f"https://api.tikwm.com/api?url={url}"
        res = requests.get(api_url, timeout=12).json()
        # Cek kalau ada link video
        video_url = res["data"]["play"] or res["data"]["play_addr"]
        file_path = "video.mp4"
        with requests.get(video_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return file_path
    except Exception as e:
        print("TikTok API error:", e)
        return None

# ===== HANDLERS =====

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

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy Caption", callback_data="copy")],
        [InlineKeyboardButton("⬇️ Download Video", callback_data="download")],
    ])

    await update.message.reply_text(
        f"📝 CAPTION (ID):\n\n{translated[:3500]}",
        reply_markup=keyboard
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
                await query.message.reply_text("❌ Gagal download TikTok, coba link lainnya.")
                return
        else:
            file_path = await download_youtube(url)

        await query.message.reply_video(video=open(file_path, "rb"))
        os.remove(file_path)
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal download:\n{e}")

# ===== MAIN =====

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(copy_caption, pattern="copy"))
    app.add_handler(CallbackQueryHandler(download_handler, pattern="download"))

    print("🤖 Bot TikTok + YouTube final siap jalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
