
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
from utils.generic import chat_message, check_chat_id
from utils.msg import MSG

class AddTradeResponses(NamedTuple):
    SYMBOL: int = 0
    MARGIN_PCT: int = 1
    LEVERAGE: int = 2
    SUMMARY: int = 3

class TestToken:
    def __init__(self, name):
        self.name = name

class AddTradeConversation:
    def __init__(self, parent, config: Config):
        self.parent = parent
        self.config = config
        self.next = AddTradeResponses()
        self.handler = ConversationHandler(
            entry_points=[CommandHandler('addtrade', self.command_addtrade)],
            states={
                self.next.SYMBOL: [MessageHandler(Filters.text & ~Filters.command, self.command_addtrade_symbol)],
                self.next.MARGIN_PCT: [MessageHandler(Filters.text & ~Filters.command, self.command_addtrade_margin_pct)],
                self.next.LEVERAGE: [MessageHandler(Filters.text & ~Filters.command, self.command_addtrade_leverage)],
                self.next.SUMMARY: [
                    CallbackQueryHandler(self.command_addtrade_summary_ok, pattern='^ok$'),
                    CallbackQueryHandler(self.command_addtrade_cancel, pattern='^cancel$'),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.command_addtrade_cancel)],
            name='addtrade_conversation',
        )

    def user_data_key(self, update: Update):
        return f'addtrade_{update_to_chat_id(update)}'

    @check_chat_id
    def command_addtrade(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        context.user_data[self.user_data_key(update)] = {}

        chat_message(update, context, text='Please send me the futures USDM trading pair symbol you want to trade. For example, enter <b>BTCUSDT</b> or <b>btcusdt</b> to trade the BTC and ETH pair.', edit=False)
        return self.next.SYMBOL

    @check_chat_id
    def command_addtrade_symbol(self, update: Update, context: CallbackContext):
        assert update.message and update.message.text and context.user_data is not None
        response = update.message.text.strip()
        symbol = None
        symbol_type = None
        symbol_type_full = 'trading'
        symbol = response.strip() # e.g BTCBUSD
        symbol_type_full = Constants.TradeType.futures
        # ToDo: verify symbol on binance
        is_valid_symbol = self.parent.futures_has_symbol(symbol)
        if is_valid_symbol is False:
            allowed = ''
            has_list = False
            if len(Config.base_assets_whitelist) > 0:
                has_list = True
                allowed = allowed + f'** Only pairs that starts with: <b>{", ".join(Config.base_assets_whitelist)}</b> are allowed.\n'
            if len(Config.base_assets_blacklist) > 0:
                has_list = True
                allowed = allowed + f'** Pairs that starts with: <b>{", ".join(Config.base_assets_blacklist)}</b> are <b>not</b> allowed.\n'
            if len(Config.quote_assets_whitelist) > 0:
                has_list = True
                allowed = allowed + f'** Only pairs that ends with: <b>{", ".join(Config.quote_assets_whitelist)}</b> are allowed.\n'
            if len(Config.quote_assets_blacklist) > 0:
                has_list = True
                allowed = allowed + f'** Pairs that ends with: <b>{", ".join(Config.quote_assets_blacklist)}</b> are <b>not</b> allowed.\n'
            if has_list:
                allowed = '<b>=== Note ===</b>\n\n' + allowed + '\n\n'
            chat_message(
                update, context, text=f'⚠️ The trading pair symbol you provided is not a valid {symbol_type_full} pair symbol. \n\n{allowed}<b>Try again:</b>', edit=False
            )
            return self.next.SYMBOL
        add = context.user_data[self.user_data_key(update)]
        add['trade_type'] = symbol_type_full
        add['symbol'] = symbol
        add['name'] = f"{symbol.upper()} {symbol_type_full.capitalize()}"

        if self.parent.trade_exists(symbol=symbol, trade_type=add['trade_type'], update=update):
            chat_message(update, context, text=f'⚠️ You already added <b>{add["name"]}</b> trade. You may want to update its settings with the <a href="/{Constants.Commands.updatetrade}">/{Constants.Commands.updatetrade}</a> command instead.', edit=False)
            del context.user_data[self.user_data_key(update)]
            return ConversationHandler.END
        chat_message(
            update,
            context,
            text=f'<i>Processing <b>{add["name"]}</b> trade...</i>\n\n'
            + (f'Now enter the percentage of BUSD or USDT to add to your margin from your futures wallet. \nFor example, enter <b>20.5</b> to use 20.5% of your futures balance has margin everytime. \n\nYou can update this later for this trade with the <a href="/{Constants.Commands.updatetrade}">/{Constants.Commands.updatetrade}</a> command.' if symbol_type == 'f' else f'Enter the percentage of BUSD or USDT to trade with in your spot wallet. For example, enter <b>20.5</b> to use 20.5% of your spot balance to trade everytime. You can update this later for this trade with the <a href="/{Constants.Commands.updatetrade}">/{Constants.Commands.updatetrade}</a> command.'),
            edit=False,
        )
        return self.next.MARGIN_PCT

    @check_chat_id
    def command_addtrade_margin_pct(self, update: Update, context: CallbackContext):
        assert update.message and update.message.text and context.user_data is not None
        add = context.user_data[self.user_data_key(update)]
        try:
            add['margin_pct'] = float(update.message.text.strip().replace('%', ''))
            if add['margin_pct'] > 100:
                add['margin_pct'] = 100
            elif add['margin_pct'] <= 0:
                add['margin_pct'] = 1
        except:
            self.error_msg(update, context, MSG.input_error)
            return self.next.MARGIN_PCT
        chat_message(
            update,
            context,
            text=f"Alright, this trade will use <b>{add['margin_pct']}%</b> of the wallet.\n\n" 
            + f'Now enter the leverage to use for the trade. For example, enter <b>10</b> to use 10x leverage. Maximum leverage is {self.parent.config.max_leverage}x. \n\nYou can update your leverage for this trade later with the <a href="/{Constants.Commands.updatetrade}">/{Constants.Commands.updatetrade}</a> command.',
            edit=False,
        )
        return self.next.LEVERAGE

    @check_chat_id
    def command_addtrade_leverage(self, update: Update, context: CallbackContext):
        assert update.message and update.message.text and context.user_data is not None
        add = context.user_data[self.user_data_key(update)]
        try:
            add['leverage'] = int(update.message.text.strip().replace('x', ''))
            if add['leverage'] <= 0:
                add['leverage'] = 1
            elif add['leverage'] > int(self.parent.config.max_leverage):
                chat_message(update, context, text=f'⚠️ Your leverage cannot be greater than {self.parent.config.max_leverage}x', edit=False)
                return self.next.LEVERAGE
        except:
            self.error_msg(update, context, MSG.input_error)
            return self.next.LEVERAGE
        chat_message(
            update,
            context,
            text=f"Ok, this trade will use <b>{add['leverage']}x</b> leverage."
            + f'\n<u>Confirm</u> the order below!',
            edit=False,
        )
        return self.print_summary(update, context)

    def print_summary(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        order = context.user_data[self.user_data_key(update)]
        symbol = order['symbol']
        trade_type = order['trade_type']
        margin_pct = order['margin_pct']
        leverage = order['leverage']

        message = (
            '<b>=== Preview Trade Settings ===</b>\n'
            + f'{trade_type.capitalize()} trade for {symbol.upper()} pair\n\n'
            + f'Margin Percentage: <b>{margin_pct}%</b>\n'
            + (f'Leverage: <b>{leverage}x</b>')
        )
        '''
        reply_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes and Don't Use Order Book Strategy", callback_data='ok'),
            ],
            [
                InlineKeyboardButton('✅ Yes and Use Order Book Strategy', callback_data='ok_order_book')
            ],
            [
                InlineKeyboardButton('❌ Cancel', callback_data='cancel'),
            ]
        ])
        '''
        reply_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes", callback_data='ok'),
                InlineKeyboardButton('❌ Cancel', callback_data='cancel'),
            ]
        ])
        chat_message(
            update,
            context,
            text=message,
            reply_markup=reply_markup,
            edit=False,
        )
        return self.next.SUMMARY
        
    @check_chat_id
    def command_addtrade_summary_ok(self, update: Update, context: CallbackContext):
        assert context.user_data is not None
        order = context.user_data[self.user_data_key(update)]
        symbol = order['symbol']
        margin_pct = order['margin_pct']
        leverage = order['leverage']

        user = self.parent.getuser(update_to_chat_id(update))

        if user is not None:
            self.parent.addtrade(
                api_key=user['key'],
                api_secret=user['secret'],
                symbol=symbol, 
                margin_pct=margin_pct, 
                leverage=leverage,
                update=update,
                context=context
            )
        else:
            chat_message(
                update,
                context,
                text=f"",
                edit=False,
            )
        return ConversationHandler.END

    @check_chat_id
    def command_addtrade_cancel(self, update: Update, context: CallbackContext):
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