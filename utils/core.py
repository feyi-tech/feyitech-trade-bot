from loguru import logger
import sqlalchemy
from telegram import Update

from utils.config import Config

def get_db(name):
    return sqlalchemy.create_engine(f'sqlite:///{name}.db')

def update_to_chat(update: Update):
    chat = None
    try:
        if update.message:
            chat = update['message']['chat']
        else:
            chat = update['callback_query']['message']['chat']
    except:
        chat = update['chat']
    return chat

def update_to_chat_id(update: Update):
    return update_to_chat(update)['id']

def is_admin(chat_id):
    return chat_id == Config.secrets.admin_chat_id

{
    'new_chat_members': [], 
    'entities': [], 'photo': [], 
    'delete_chat_photo': False, 
    'new_chat_photo': [], 
    'message_id': 1971, 'date': 1656771267, 
    'chat': {'username': 'tronpipe', 'first_name': 'Tron', 'type': 'private', 'last_name': 'Pipe', 'id': 916028969}, 'caption_entities': [], 'group_chat_created': False, 'supergroup_chat_created': False, 'channel_chat_created': False, 'text': "⛔️ Exception while handling an update\n'bool' object has no attribute 'message'", 'from': {'username': 'feyi_tech_trade_bot', 'first_name': 'FeyiTechTradeBot', 'id': 5544021987, 'is_bot': True}}