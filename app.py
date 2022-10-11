#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the CC0 license.

"""
First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
"""
import logging, os, asyncio, base64
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from torchvision.utils import draw_bounding_boxes
from torchvision.io import read_image, write_png
from torch import tensor
from deepgram import Deepgram
from google.cloud import aiplatform

load_dotenv()
dg_client = Deepgram(os.getenv('DEEPGRAM_API'))
endpoint = aiplatform.Endpoint('projects/73250724104/locations/us-central1/endpoints/4349496475667922944')

# Enable logging
logging.basicConfig(filename='log.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filemode='a', level=logging.INFO)
logger = logging.getLogger(__name__)


def encode_image(image):
    with open(image, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    return encoded_string

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi!')

def text (update, context):
    """Echo the user message."""
    update.message.reply_text('This bot detects objects in images. Send over a pic to try it out.')

def image(update, context):
    # https://stackoverflow.com/questions/50388435/how-save-photo-in-telegram-python-bot
    image_file = context.bot.get_file(update.message.photo[-1].file_id)
    image_file.download('image.jpg')
    update.message.reply_text('Image received, predictions available shortly.')

    image_encoded = encode_image('image.jpg')
    instance = [{
        "data": {
            "b64": str(image_encoded.decode('utf-8'))
        }
    }]
    prediction = endpoint.predict(instances=instance)
    # print(f"{prediction[0][0]}")
    im = read_image('image.jpg')
    boxes, labels = [], [] 
    for obj in prediction[0][0]:
        for k in obj:
            if k != 'score':
                labels.append(k)
                boxes.append(obj[k])
    predictions = draw_bounding_boxes(im, boxes=tensor(boxes), labels=labels, font_size=50, width=3, colors='red')
    write_png(predictions,'predictions.png')
    update.message.reply_photo(open('predictions.png', 'rb'))

def voice(update, context):
    '''Parse audio recording'''
    # https://docs.python-telegram-bot.org/en/stable/telegram.message.html?highlight=reply_text#telegram.Message.reply_text
    # Get audio file
    audio_file = context.bot.get_file(update.message.voice.file_id)
    audio_file.download(f"voice_note.ogg")
    update.message.reply_text('Recording received, transcript available shortly.')

    # Get transcript
    async def test():
        with open('voice_note.ogg', 'rb') as audio:
            source = {'buffer': audio, 'mimetype': 'audio/ogg'}
            response = await dg_client.transcription.prerecorded(source, {'punctuate': True})
        return response
    response = asyncio.run(test())
    transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
    logger.info(transcript)

    # Return generated transcript
    update.message.reply_text(transcript)

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(os.getenv('TELEGRAM'), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))

    # on noncommand i.e message
    dp.add_handler(MessageHandler(Filters.text, text))
    dp.add_handler(MessageHandler(Filters.photo, image))
    dp.add_handler(MessageHandler(Filters.voice, voice))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()