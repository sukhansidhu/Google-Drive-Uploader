#!/usr/bin/env python3

import os
import re
import json
from time import time
from telegram import ParseMode, Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    Updater,
    CallbackContext,
)
from telegram.ext.dispatcher import run_async
from pySmartDL import SmartDL
from pydrive.auth import GoogleAuth
from plugins import TEXT
from plugins.tok_rec import is_token
from plugins.dpbox import DPBOX
from plugins.wdl import wget_dl
from creds import Creds
from upload import upload
from mega import Mega

# Google Auth
gauth = GoogleAuth()

# Bot Token and Dispatcher
bot_token = Creds.TG_TOKEN
updater = Updater(token=bot_token, workers=8, use_context=True)
dp = updater.dispatcher

# /start
@run_async
def start(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=TEXT.START.format(update.effective_user.first_name),
        parse_mode=ParseMode.HTML
    )

# /help
@run_async
def help_cmd(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=TEXT.HELP,
        parse_mode=ParseMode.HTML
    )

# /auth
@run_async
def auth(update: Update, context: CallbackContext):
    ID = str(update.effective_user.id)
    try:
        if os.path.exists(ID):
            gauth.LoadCredentialsFile(ID)
    except Exception as e:
        print("Credential load error:", e)

    if gauth.credentials is None:
        try:
            authurl = gauth.GetAuthUrl()
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=TEXT.AUTH_URL.format(authurl),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print("Auth URL error:", e)
    elif gauth.access_token_expired:
        gauth.Refresh()
        gauth.SaveCredentialsFile(ID)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Token refreshed.")
    else:
        gauth.Authorize()
        context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.ALREADY_AUTH)

# Token receiver
@run_async
def token(update: Update, context: CallbackContext):
    msg = update.message.text
    ID = str(update.effective_user.id)

    if is_token(msg):
        token = msg.split()[-1]
        try:
            gauth.Auth(token)
            gauth.SaveCredentialsFile(ID)
            context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.AUTH_SUCC)
        except Exception as e:
            print("Auth error:", e)
            context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.AUTH_ERROR)

# /revoke
@run_async
def revoke_tok(update: Update, context: CallbackContext):
    ID = str(update.effective_chat.id)
    try:
        os.remove(ID)
        context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.REVOKE_TOK)
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.REVOKE_FAIL)

# File uploader
@run_async
def UPLOAD(update: Update, context: CallbackContext):
    url = update.message.text.split()[-1]
    ID = str(update.effective_chat.id)

    if not os.path.isfile(ID):
        context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.NOT_AUTH)
        return

    sent_message = context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.PROCESSING)
    filename = ""
    DownloadStatus = False

    try:
        if "dropbox.com" in url:
            url = DPBOX(url)
            sent_message.edit_text(TEXT.DP_DOWNLOAD)
            filename = wget_dl(url)
            sent_message.edit_text(TEXT.DOWN_COMPLETE)
            DownloadStatus = True

        elif "mega.nz" in url:
            sent_message.edit_text(TEXT.DOWN_MEGA)
            m = Mega.from_credentials(TEXT.MEGA_EMAIL, TEXT.MEGA_PASSWORD)
            filename = m.download_from_url(url)
            sent_message.edit_text(TEXT.DOWN_COMPLETE)
            DownloadStatus = True

        else:
            sent_message.edit_text(TEXT.DOWNLOAD)
            filename = wget_dl(url)
            sent_message.edit_text(TEXT.DOWN_COMPLETE)
            DownloadStatus = True

    except Exception as e:
        print("Download error:", e)
        if TEXT.DOWN_TWO:
            try:
                sent_message.edit_text(f"Retrying with SmartDL: {e}")
                obj = SmartDL(url)
                obj.start()
                filename = obj.get_dest()
                DownloadStatus = True
            except Exception as e:
                print("SmartDL error:", e)
                sent_message.edit_text(f"SmartDL Error: {e}")
                return
        else:
            sent_message.edit_text(f"Download failed: {e}")
            return

    try:
        if "error" in filename:
            sent_message.edit_text("Filename error")
            os.remove(filename)
            return

        if DownloadStatus:
            sent_message.edit_text(TEXT.UPLOADING)
            SIZE = round(os.path.getsize(filename) / 1048576)
            FILENAME = os.path.basename(filename)
            FILELINK = upload(filename, update, context, TEXT.drive_folder_name)
            sent_message.edit_text(
                TEXT.DOWNLOAD_URL.format(FILENAME, SIZE, FILELINK),
                parse_mode=ParseMode.HTML
            )
            os.remove(filename)

    except Exception as e:
        print("Upload error:", e)
        sent_message.edit_text(f"Upload failed: {e}")
        if os.path.exists(filename):
            os.remove(filename)

# /update
def status(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text=TEXT.UPDATE, parse_mode=ParseMode.HTML)

# ─── HANDLERS ─────────────────────────────────────────
dp.add_handler(CommandHandler('start', start))
dp.add_handler(CommandHandler('help', help_cmd))
dp.add_handler(CommandHandler('auth', auth))
dp.add_handler(CommandHandler('revoke', revoke_tok))
dp.add_handler(CommandHandler('update', status))

dp.add_handler(MessageHandler(Filters.regex(r'http'), UPLOAD))
dp.add_handler(MessageHandler(Filters.text, token))

# ─── START BOT ────────────────────────────────────────
updater.start_polling()
updater.idle()
