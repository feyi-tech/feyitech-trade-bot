
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
from utils.generic import chat_message, check_chat_id, get_trade_path
from utils.msg import MSG

class StopTradeResponses(NamedTuple):
    CONFIRM: int = 0

class StopTradeConversation:
    def __init__(self, parent, config: Config):
        self.parent = parent
        self.config = config
        self.next = StopTradeResponses()
        self.handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.command_stoptrade, pattern='^stoptrade:[^:]*$')],
            states={
                self.next.CONFIRM: [CallbackQueryHandler(self.command_stoptrade_confirm)],
            },
            fallbacks=[CommandHandler('cancel', self.command_stoptrade_cancel)],
            name='stoptrade_conversation',
        )

    @check_chat_id
    def command_stoptrade(self, update: Update, context: CallbackContext):
        assert update.callback_query
        query = update.callback_query
        assert query.data
        query.delete_message()
        trade_keys = query.data.split(':')[1].split(Constants.trade_keys_separator)
        trade_type = trade_keys[0]
        trade_symbol = trade_keys[1]
        if not self.parent.trade_exists(symbol=trade_symbol, trade_type=trade_type, update=update):
            chat_message(update, context, text='⛔️ Invalid trade.', edit=False)
            return ConversationHandler.END
        
        trader = self.parent.get_trade(symbol=trade_symbol, trade_type=trade_type, update=update)
        chat_message(
            update,
            context,
            text=f'Do you want to <b>pause</b> or <b>remove</b> the <b>{trader.name}</b> trade?',
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton('⏸ Pause', callback_data=get_trade_path(trade_type=trade_type, trade_symbol=trade_symbol)),
                        InlineKeyboardButton('🚮 Remove/Delete', callback_data=f'{get_trade_path(trade_type=trade_type, trade_symbol=trade_symbol)}{Constants.trade_keys_separator}delete'),
                    ],
                    [
                        InlineKeyboardButton('❌ Cancel', callback_data='cancel'),
                    ]
                ]
            ),
            edit=False,
        )
        return self.next.CONFIRM

    @check_chat_id
    def command_stoptrade_confirm(self, update: Update, context: CallbackContext):
        assert update.callback_query and update.effective_chat
        query = update.callback_query
        assert query.data
        if query.data == 'cancel':
            self.cancel_command(update, context)
            return ConversationHandler.END
        trade_keys = query.data.split(Constants.trade_keys_separator)
        trade_type = trade_keys[0]
        trade_symbol = trade_keys[1]
        if not self.parent.trade_exists(symbol=trade_symbol, trade_type=trade_type, update=update):
            chat_message(update, context, text='⛔️ Invalid trade.', edit=False)
            return ConversationHandler.END
        
        self.parent.stoptrade(
            symbol=trade_symbol, 
            trade_type=trade_type,
            delete=len(trade_keys) > 2 and trade_keys[2] == 'delete',
            update=update,
            context=context
        )
        return ConversationHandler.END

    @check_chat_id
    def command_stoptrade_cancel(self, update: Update, context: CallbackContext):
        self.cancel_command(update, context)
        return ConversationHandler.END

    def cancel_command(self, update: Update, context: CallbackContext):
        chat_message(update, context, text='⚠️ OK, I\'m cancelling this command.', edit=False)