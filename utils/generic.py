
import logging
import time
from loguru import logger
import functools
from typing import Any, Callable, Iterable, List, Mapping, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler, Defaults, Updater

from utils.constants import Constants
from utils.core import update_to_chat
from utils.trade_logger import filelog


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def check_chat_id(func: Callable) -> Callable:
    """Compare chat ID with users list and refuse access if unauthorized."""

    @functools.wraps(func)
    def wrapper_check_chat_id(this, update: Update, context: CallbackContext, *args, **kwargs):
        if update.callback_query:
            update.callback_query.answer()
        if update.effective_chat is None:
            logger.debug('No chat ID')
            return
        if context.user_data is None:
            logger.debug('No user data')
            return
        if update.message is None and update.callback_query is None:
            logger.debug('No message')
            return
        if update.message and update.message.text is None and update.callback_query is None:
            logger.debug('No text in message')
            return
        chat_id = update.effective_chat.id

        signed = False
        users = 0
        try:
            signed = this.signed_up(chat_id)
            users = this.users
        except:
            signed = this.parent.signed_up(chat_id)
            users = this.parent.users

        if chat_id == this.config.secrets.admin_chat_id or signed is True:
            try:
                this.setupuser(update)
            except:
                this.parent.setupuser(update)
            return func(this, update, context, *args, **kwargs)
        logger.warning(f'Prevented user {chat_id} to interact.')
        context.bot.send_message(
            chat_id=this.config.secrets.admin_chat_id, text=f'Prevented user to interact. ID: {chat_id} | Username: {update_to_chat(update)["username"]} | SignedUp: {signed} | Users: {users}'
        )
        context.bot.send_message(chat_id=chat_id, text=f'This bot is not public, you are not allowed to use it. Your telegram ID is {chat_id}. Send it to the admin to add you.')

    return wrapper_check_chat_id


def only_admin(func: Callable) -> Callable:
    """Compare chat ID with admin's chat ID and refuse access if unauthorized."""

    @functools.wraps(func)
    def wrapper_check_chat_id(this, update: Update, context: CallbackContext, *args, **kwargs):
        if update.callback_query:
            update.callback_query.answer()
        if update.effective_chat is None:
            logger.debug('No chat ID')
            return
        if context.user_data is None:
            logger.debug('No user data')
            return
        if update.message is None and update.callback_query is None:
            logger.debug('No message')
            return
        if update.message and update.message.text is None and update.callback_query is None:
            logger.debug('No text in message')
            return
        chat_id = update.effective_chat.id

        if chat_id == this.config.secrets.admin_chat_id:
            try:
                this.setupuser(update)
            except:
                this.parent.setupuser(update)
            return func(this, update, context, *args, **kwargs)
        logger.warning(f'Prevented non admin {chat_id} to interact.')
        context.bot.send_message(
            chat_id=this.config.secrets.admin_chat_id, text=f'Prevented non admin to interact. ID: {chat_id} | Username: {update_to_chat(update)["username"]}'
        )
        context.bot.send_message(chat_id=chat_id, text='Only the admin can perfom this action. Contact the admin for more info.')

    return wrapper_check_chat_id

def chat_doc(
    update: Update,
    context: CallbackContext,
    path: str
) -> Optional[Message]:
    assert update.effective_chat
    try:
        document = open(path, 'rb')
        return context.bot.send_document(chat_id=update.effective_chat.id, document=document)
    except Exception as e:
        #filelog(f'{Constants.log_dir_name}/{Constants.error_log_filename}', str(e) + Constants.log_text_nl)
        a = 1

def chat_photo(
    update: Update,
    context: CallbackContext,
    path: str
) -> Optional[Message]:
    assert update.effective_chat
    photo = open(path, 'rb')
    return context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)

def chat_message_only(
    update: Update,
    context: CallbackContext,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    edit: bool = False
) -> Optional[Message]:
    assert update.effective_chat
    if update.callback_query is not None and edit:
        query = update.callback_query
        try:
            query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
            )
        except Exception as e:  # if the message did not change, we can get an exception, we ignore it
            if not str(e).startswith('Message is not modified'):
                logger.error(f'Exception during message update: {e}')
                context.bot.send_message(chat_id=update.effective_chat.id, text=f'Exception during message update: {e}')
        return None
    return context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

def chat_message(
    update: Update,
    context: CallbackContext,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    edit: bool = False,
    photo_up: str = None,
    photo_down: str = None,
    doc: str = None,
    docs: List[str] = []
) -> Optional[Message]:
    if photo_up is not None:
        chat_photo(update=update, context=context, path=photo_up)
        time.sleep(0.2)
    if text is not None or reply_markup is not None:
        chat_message_only(update=update, context=context, text=text, reply_markup=reply_markup, edit=edit)
    if doc is not None or len(docs) > 0:
        if doc is not None:
            docs.insert(0, doc)
        for d in docs:
            chat_doc(update=update, context=context, path=d)
    if photo_down is not None:
        chat_photo(update=update, context=context, path=photo_down)
    


def get_trade_path(trade_type=str, trade_symbol=str):
    return f'{trade_type}{Constants.trade_keys_separator}{trade_symbol}'

def get_trades_keyboard_layout(
    spot_trades: Mapping, futures_trades: Mapping,
    callback_prefix: Optional[str] = None,
    order_by: Optional[str] = None,  
    per_row: int = 2
) -> List[List[InlineKeyboardButton]]:
    spot_buttons = []
    futures_buttons = []
    final_buttons = []

    '''
    Inline KeyBoard Layout
    [
        [
            InlineKeyboardButton('1%', callback_data='1'),
            InlineKeyboardButton('2%', callback_data='2'),
            InlineKeyboardButton('5%', callback_data='5'),
            InlineKeyboardButton('10%', callback_data='10'),
        ],
        [
            InlineKeyboardButton('No trailing stop loss', callback_data='None'),
            InlineKeyboardButton('❌ Cancel', callback_data='cancel'),
        ],
    ]
    '''

    if len(spot_trades) > 0:
        for trader in sorted(spot_trades.values(), key=lambda trader: trader.symbol):
            trade_key = get_trade_path(trade_type=Constants.TradeType.spot, trade_symbol=trader.symbol)
            logger.info(trade_key)
            callback = f'{callback_prefix}:{trade_key}' if callback_prefix else trade_key
            spot_buttons.append(InlineKeyboardButton(trader.name, callback_data=callback))
        final_buttons = [spot_buttons[i : i + per_row] for i in range(0, len(spot_buttons), per_row)]
    
    if len(futures_trades) > 0:
        for trader in sorted(futures_trades.values(), key=lambda trader: trader.symbol):
            trade_key = get_trade_path(trade_type=Constants.TradeType.futures, trade_symbol=trader.symbol)
            logger.info(trade_key)
            callback = f'{callback_prefix}:{trade_key}' if callback_prefix else trade_key
            futures_buttons.append(InlineKeyboardButton(trader.name, callback_data=callback))
        final_buttons = final_buttons + [futures_buttons[i : i + per_row] for i in range(0, len(futures_buttons), per_row)]
    all_buttons = spot_buttons + futures_buttons
    
    # l1 = [1,2,3,4], l2 = [5,6,7,8] per_row = 2
    # [ l1[i : i + per_row] for i in range(0, len(l1), per_row)] => [ [1,2], [3,4] ]
    # [
    #   [ l1[i : i + per_row] for i in range(0, len(l1), per_row)] => [ [1,2], [3,4] ],
    #   [ l2[i : i + per_row] for i in range(0, len(l2), per_row)] => [ [1,2], [3,4] ]
    # ] => 
    # [ [[1, 2], [3, 4]], [[5, 6], [7, 8]] ]
    if len(all_buttons) > 0:
        final_buttons = final_buttons + [[InlineKeyboardButton('❌ Cancel Action', callback_data='removetradechoice')]]

    logger.info("buttons::")
    logger.info(spot_buttons)
    logger.info(futures_buttons)
    logger.info(final_buttons)
    return final_buttons