
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
from utils.generic import chat_message, only_admin, get_trade_path, only_admin
from utils.msg import MSG

class RemoveUserResponses(NamedTuple):
    CONFIRM: int = 0

class RemoveUserConversation:
    def __init__(self, parent, config: Config):
        self.parent = parent
        self.config = config
        self.next = RemoveUserResponses()
        self.handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.command_removeuser, pattern='^removeuser:[^:]*$')],
            states={
                self.next.CONFIRM: [CallbackQueryHandler(self.command_removeuser_confirm)],
            },
            fallbacks=[CommandHandler('cancel', self.command_removeuser_cancel)],
            name='removeuser_conversation',
        )

    @only_admin
    def command_removeuser(self, update: Update, context: CallbackContext):
        assert update.callback_query
        query = update.callback_query
        assert query.data
        query.delete_message()
        user_id = query.data.split(':')[1].strip()
        if not self.parent.signed_up(id=user_id):
            chat_message(update, context, text='⛔️ User does not exist.', edit=False)
            return ConversationHandler.END
        
        chat_message(
            update,
            context,
            text=f'Do you want to remove the user with id the <b>{user_id}</b>?',
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton('✅ Yes', callback_data=user_id)
                    ],
                    [
                        InlineKeyboardButton('❌ No', callback_data='cancel'),
                    ]
                ]
            ),
            edit=False,
        )
        return self.next.CONFIRM

    @only_admin
    def command_removeuser_confirm(self, update: Update, context: CallbackContext):
        assert update.callback_query and update.effective_chat
        query = update.callback_query
        assert query.data
        if query.data == 'cancel':
            self.cancel_command(update, context)
            return ConversationHandler.END
        user_id = query.data.strip()
        if not self.parent.signed_up(id=user_id):
            chat_message(update, context, text='⛔️ User does not exist.', edit=False)
            return ConversationHandler.END
        
        self.parent.removeuser(
            id=user_id,
            update=update,
            context=context
        )
        return ConversationHandler.END

    @only_admin
    def command_removeuser_cancel(self, update: Update, context: CallbackContext):
        self.cancel_command(update, context)
        return ConversationHandler.END

    def cancel_command(self, update: Update, context: CallbackContext):
        chat_message(update, context, text='⚠️ OK, I\'m cancelling this command.', edit=False)