
from datetime import datetime
from decimal import Decimal
from typing import Mapping, NamedTuple
from loguru import logger

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
)
from utils.config import Config
from utils.constants import Constants
from utils.core import update_to_chat_id
from utils.generic import chat_message, only_admin, only_admin
from utils.msg import MSG

class AddUserResponses(NamedTuple):
    USER_ID: int = 0
    KEY: int = 1
    SECRET: int = 2
    CONFIRM: int = 3

class TestToken:
    def __init__(self, name):
        self.name = name

class AddUserConversation:
    def __init__(self, parent, config: Config):
        self.parent = parent
        self.config = config
        self.next = AddUserResponses()
        self.handler = ConversationHandler(
            entry_points=[CommandHandler('adduser', self.command_adduser)],
            states={
                self.next.USER_ID: [MessageHandler(Filters.text & ~Filters.command, self.command_adduser_id)],
                self.next.KEY: [MessageHandler(Filters.text & ~Filters.command, self.command_adduser_key)],
                self.next.SECRET: [MessageHandler(Filters.text & ~Filters.command, self.command_adduser_secret)],
                self.next.CONFIRM: [
                    CallbackQueryHandler(self.command_adduser_ok, pattern='^ok$'),
                    CallbackQueryHandler(self.command_adduser_cancel, pattern='^cancel$'),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.command_adduser_cancel)],
            name='adduser_conversation',
        )

    def user_data_key(self, update: Update):
        return f'adduser_{update_to_chat_id(update)}'

    @only_admin
    def command_adduser(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        context.user_data[self.user_data_key(update)] = {}

        chat_message(update, context, text='Please send me the ID of the user to add.', edit=False)
        return self.next.USER_ID

    @only_admin
    def command_adduser_id(self, update: Update, context: CallbackContext):
        assert update.message and update.message.text and context.user_data is not None
        response = update.message.text.strip()
        addlog = context.user_data[self.user_data_key(update)]
        addlog['id'] = response

        if self.parent.signed_up(id=addlog['id']):
            chat_message(update, context, text=f'⚠️ User already added', edit=False)
            del context.user_data[self.user_data_key(update)]
            return ConversationHandler.END
        chat_message(
            update,
            context,
            text=f"<b>Enter User's Binance API KEY:\n</b>",
            edit=False,
        )
        return self.next.KEY
    
    @only_admin
    def command_adduser_key(self, update: Update, context: CallbackContext):
        assert update.message and update.message.text and context.user_data is not None
        response = update.message.text.strip()
        addlog = context.user_data[self.user_data_key(update)]
        addlog['key'] = response

        if len(addlog['key']) == 0:
            chat_message(update, context, text=f"<b>⚠️ No Key entered. Enter User's Binance API KEY:\n</b>", edit=False)
            del context.user_data[self.user_data_key(update)]
            return self.next.KEY
        chat_message(
            update,
            context,
            text=f"<b>Enter User's Binance API SECRET:\n</b>",
            edit=False,
        )
        return self.next.SECRET

    @only_admin
    def command_adduser_secret(self, update: Update, context: CallbackContext):
        assert update.message and update.message.text and context.user_data is not None
        response = update.message.text.strip()
        addlog = context.user_data[self.user_data_key(update)]
        addlog['secret'] = response

        if len(addlog['secret']) == 0:
            chat_message(update, context, text=f"<b>⚠️ No Key entered. Enter User's Binance API SECRET:\n</b>", edit=False)
            del context.user_data[self.user_data_key(update)]
            return self.next.SECRET
        chat_message(
            update,
            context,
            text=f'<b>Confirm Action below...</b>',
            edit=False,
        )
        return self.print_summary(update, context)

    def print_summary(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        addlog = context.user_data[self.user_data_key(update)]
        id = addlog['id']
        
        chat_message(
            update,
            context,
            text=f'Are you sure you want to add Id {id}?',
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton('✅ Confirm', callback_data='ok'),
                        InlineKeyboardButton('❌ Cancel', callback_data='cancel'),
                    ]
                ]
            ),
            edit=False,
        )
        return self.next.CONFIRM
        
    @only_admin
    def command_adduser_ok(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        addlog = context.user_data[self.user_data_key(update)]
        id = addlog['id']
        key = addlog['key']
        secret = addlog['secret']

        self.parent.adduser(
            id=id,
            key=key,
            secret=secret,
            update=update,
            context=context
        )
        return ConversationHandler.END

    @only_admin
    def command_adduser_cancel(self, update: Update, context: CallbackContext):
        self.cancel_command(update, context)
        return ConversationHandler.END

    def cancel_command(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        del context.user_data[self.user_data_key(update)]
        chat_message(update, context, text='⚠️ OK, I\'m cancelling this command.', edit=False)

    def error_msg(self, update: Update, context: CallbackContext, text: str):
        chat_message(update, context, text=f'{text}', edit=False)

    def command_error(self, update: Update, context: CallbackContext, text: str):
        assert context.user_data is not None
        del context.user_data[self.user_data_key(update)]
        chat_message(update, context, text=f'⛔️ {text}', edit=False)