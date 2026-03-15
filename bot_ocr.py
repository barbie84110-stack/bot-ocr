#!/usr/bin/env python3
"""
Bot Telegram — OCR uniquement
Installation :
  pip install python-telegram-bot pytesseract Pillow
  Tesseract :
    Windows → https://github.com/UB-Mannheim/tesseract/wiki
    Linux   → sudo apt install tesseract-ocr tesseract-ocr-fra
    macOS   → brew install tesseract tesseract-lang
"""

import os
import sys
import logging
import platform

from io import BytesIO
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)

# ================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "METS_TON_TOKEN_ICI")
# ================================================================

# Auto-détection Tesseract Windows
if platform.system() == "Windows":
    _p = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_p):
        pytesseract.pytesseract.tesseract_cmd = _p

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
#  OCR
# ════════════════════════════════════════════════════════════════

def _preprocess(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    w, h = img.size
    if w < 800:
        s   = 800 / w
        img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    return img


def ocr(image_bytes: bytes) -> str:
    img = _preprocess(Image.open(BytesIO(image_bytes)))
    try:
        return pytesseract.image_to_string(img, lang="fra+eng").strip()
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(img, lang="eng").strip()


async def _handle_image(update: Update, image_bytes: bytes):
    try:
        text = ocr(image_bytes)
    except Exception as ex:
        await update.message.reply_text(
            f"❌ Erreur OCR : {ex}\n\nVérifie que Tesseract est installé."
        )
        return

    if not text:
        await update.message.reply_text("❌ Aucun texte détecté sur l'image.")
        return

    # Découpe en morceaux si trop long (limite Telegram = 4096 chars)
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for i, chunk in enumerate(chunks):
        header = f"📄 <b>Texte extrait</b> (partie {i+1}/{len(chunks)}) :\n\n" if len(chunks) > 1 else "📄 <b>Texte extrait :</b>\n\n"
        await update.message.reply_text(
            header + f"<pre>{chunk}</pre>",
            parse_mode="HTML",
        )


# ════════════════════════════════════════════════════════════════
#  HANDLERS
# ════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salut ! Envoie-moi une photo ou une image et j'en extrais le texte.\n\n"
        "Fonctionne avec : photos, screenshots, documents scannés, étiquettes…"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>Comment utiliser :</b>\n\n"
        "• Envoie une <b>photo</b> directement\n"
        "• Ou envoie un fichier image (PNG, JPG, WEBP…)\n\n"
        "Je détecte le français et l'anglais automatiquement.",
        parse_mode="HTML",
    )

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Analyse en cours…")
    try:
        file  = await ctx.bot.get_file(update.message.photo[-1].file_id)
        data  = bytes(await file.download_as_bytearray())
        await _handle_image(update, data)
    except Exception as ex:
        await update.message.reply_text(f"❌ Erreur : {ex}")

async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await update.message.reply_text("⚠️ Envoie uniquement des images.")
        return
    await update.message.reply_text("🔍 Analyse en cours…")
    try:
        file = await ctx.bot.get_file(doc.file_id)
        data = bytes(await file.download_as_bytearray())
        await _handle_image(update, data)
    except Exception as ex:
        await update.message.reply_text(f"❌ Erreur : {ex}")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Envoie-moi une image pour extraire le texte.")


# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════

def main():
    try:
        pytesseract.get_tesseract_version()
        logger.info("✅ Tesseract OK")
    except pytesseract.TesseractNotFoundError:
        logger.warning(
            "⚠️ Tesseract introuvable.\n"
            "  Windows : https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  Linux   : sudo apt install tesseract-ocr tesseract-ocr-fra\n"
            "  macOS   : brew install tesseract tesseract-lang"
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(MessageHandler(filters.PHOTO,               handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE,      handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🤖 Bot OCR démarré…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
