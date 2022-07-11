
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
from utils.generic import chat_message, check_chat_id, get_trade_path
from utils.msg import MSG

class UpdateTradeResponses(NamedTuple):
    MARGIN_PCT: int = 0
    LEVERAGE: int = 1
    SUMMARY: int = 2

class UpdateTradeConversation:
    def __init__(self, parent, config: Config):
        self.parent = parent
        self.config = config
        self.next = UpdateTradeResponses()
        self.handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.command_updatetrade, pattern='^updatetrade:[^:]*$')],
            states={
                self.next.MARGIN_PCT: [
                    MessageHandler(Filters.text & ~Filters.command, self.command_updatetrade_margin_pct),
                    CallbackQueryHandler(self.command_updatetrade_margin_pct, pattern='^keep$')
                ],
                self.next.LEVERAGE: [
                    MessageHandler(Filters.text & ~Filters.command, self.command_updatetrade_leverage),
                    CallbackQueryHandler(self.command_updatetrade_leverage, pattern='^keep$')
                ],
                self.next.SUMMARY: [
                    CallbackQueryHandler(self.command_updatetrade_summary_ok, pattern='^ok$'),
                    CallbackQueryHandler(self.command_updatetrade_summary_ok_ob, pattern='^ok_order_book$'),
                    CallbackQueryHandler(self.command_updatetrade_cancel, pattern='^cancel$'),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.command_updatetrade_cancel)],
            name='updatetrade_conversation',
        )

    def user_data_key(self, update: Update):
        return f'updatetrade_{update_to_chat_id(update)}'

    @check_chat_id
    def command_updatetrade(self, update: Update, context: CallbackContext):
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
        context.user_data[self.user_data_key(update)] = {}
        update_ = context.user_data[self.user_data_key(update)]
        update_['symbol'] = trade_symbol
        update_['name'] = trader.name
        update_['trade_type'] = trade_type
        update_['is_futures'] = True # trader.is_futures
        update_['margin_pct'] = trader.margin_pct
        update_['leverage'] = trader.leverage
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f'✅ Keep Using {trader.margin_pct}%', callback_data='keep')]
            ]
        )
        chat_message(
            update,
            context,
            text=(f'Enter the percentage of BUSD or USDT to add to your margin from your futures wallet. \n\n The current margin percentage is <b>{trader.margin_pct}</b>%.'),
            reply_markup=reply_markup,
            edit=False,
        )
        return self.next.MARGIN_PCT


    @check_chat_id
    def command_updatetrade_margin_pct(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        update_ = context.user_data[self.user_data_key(update)]
        if update.message:
            assert update.message.text
            try:
                pct = update.message.text.strip().replace('%', '')
                update_['margin_pct'] = float(pct)
                if update_['margin_pct'] > 100:
                    update_['margin_pct'] = 100 
            except:
                chat_message(update, context, text=MSG.input_error, edit=False)
                return self.next.MARGIN_PCT
        if update_['is_futures']:
            reply_markup = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(f"✅ Keep Using {update_['leverage']}x", callback_data='keep')]
                ]
            )
            chat_message(
                update,
                context,
                text=f"Alright, this trade will use <b>{update_['margin_pct']}%</b> of the wallet.\n\n" 
                + f"Now enter the leverage the trade should switch to. Maximum leverage is {self.parent.config.max_leverage}x. \n\nThe current leverage is <b>{update_['leverage']}</b>x.",
                reply_markup=reply_markup,
                edit=False,
            )
            return self.next.LEVERAGE
        else:
            chat_message(
                update,
                context,
                text=f"Alright, this trade will use <b>{update_['margin_pct']}%</b> of the wallet." 
                + f'\n<u>Confirm</u> the update below!',
                edit=False,
            )
            return self.print_summary(update, context)


    @check_chat_id
    def command_updatetrade_leverage(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        update_ = context.user_data[self.user_data_key(update)]
        if update.message:
            assert update.message.text
            try:
                leverage = update.message.text.strip().replace('x', '')
                if len(leverage) > 0:
                    update_['leverage'] = int(leverage)
                    if update_['leverage'] > int(self.parent.config.max_leverage):
                        chat_message(update, context, text=f'⚠️ Your leverage cannot be greater than <b>{self.parent.config.max_leverage}x</b>', edit=False)
                        return self.next.LEVERAGE
            except:
                chat_message(update, context, text=MSG.input_error, edit=False)
                return self.next.LEVERAGE
        chat_message(
            update,
            context,
            text=f"Ok, this trade will use <b>{update_['leverage']}x</b> leverage."
            + f'\n<u>Confirm</u> the update below!',
            edit=False,
        )
        return self.print_summary(update, context)

    def print_summary(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        update_ = context.user_data[self.user_data_key(update)]
        symbol = update_['symbol']
        trade_type = update_['trade_type']
        is_futures = update_['is_futures']
        margin_pct = update_['margin_pct']
        leverage = update_['leverage'] if is_futures else None

        message = (
            '<b>=== Preview Trade Settings ===</b>\n'
            + f'{trade_type.capitalize()} trade for {symbol.upper()} pair\n\n'
            + f'{"Margin Percentage" if is_futures else "Spot BUSD/USDT Percentage"}: <b>{margin_pct}%</b>\n'
            + (f'Leverage: <b>{leverage}x</b>' if is_futures else '')
        )
        chat_message(
            update,
            context,
            text=message,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Yes and Don't Use Order Book Strategy", callback_data='ok'),
                    ],
                    [
                        InlineKeyboardButton('✅ Yes and Use Order Book Strategy', callback_data='ok_order_book')
                    ],
                    [
                        InlineKeyboardButton('❌ Cancel', callback_data='cancel'),
                    ]
                ]
            ),
            edit=False,
        )
        return self.next.SUMMARY

    @check_chat_id
    def command_updatetrade_summary_ok(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        update_ = context.user_data[self.user_data_key(update)]
        symbol = update_['symbol']
        name = update_['name']
        is_futures = update_['is_futures']
        margin_pct = update_['margin_pct']
        leverage = update_['leverage']

        trade_type = Constants.TradeType.futures if is_futures else Constants.TradeType.spot
        trader = self.parent.get_trade(symbol=symbol, trade_type=trade_type, update=update)
        if trader.margin_pct == margin_pct and trader.leverage == leverage:
            chat_message(update, context, text=f'No changes made. {name} trade will continue to use its settings.', edit=False)
        else:
            self.parent.updatetrade(
                symbol=symbol,
                is_futures=is_futures,
                margin_pct=margin_pct, 
                leverage=leverage,
                use_order_book=False,
                update=update,
                context=context
            )
        return ConversationHandler.END

    @check_chat_id
    def command_updatetrade_summary_ok_ob(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        update_ = context.user_data[self.user_data_key(update)]
        symbol = update_['symbol']
        name = update_['name']
        is_futures = update_['is_futures']
        margin_pct = update_['margin_pct']
        leverage = update_['leverage']

        trade_type = Constants.TradeType.futures if is_futures else Constants.TradeType.spot
        trader = self.parent.get_trade(symbol=symbol, trade_type=trade_type, update=update)
        if trader.margin_pct == margin_pct and trader.leverage == leverage:
            chat_message(update, context, text=f'No changes made. {name} trade will continue to use its settings.', edit=False)
        else:
            self.parent.updatetrade(
                symbol=symbol,
                is_futures=is_futures,
                margin_pct=margin_pct, 
                leverage=leverage,
                use_order_book=True,
                update=update,
                context=context
            )
        return ConversationHandler.END

    @check_chat_id
    def command_updatetrade_cancel(self, update: Update, context: CallbackContext):
        self.cancel_command(update, context)
        return ConversationHandler.END

    def cancel_command(self, update: Update, context: CallbackContext):
        chat_message(update, context, text='⚠️ OK, I\'m cancelling this command.', edit=False)