import os
import datetime as DT
from loguru import logger
import pandas as pd
import sqlalchemy
from binance.client import Client
from binance import BinanceSocketManager
from symbol_info import SymbolInfo
from utils.asiko import time_diff_now
from utils.config import Config

from utils.core import update_to_chat_id
from utils.constants import Constants
from utils.generic import chat_message, check_chat_id, get_trade_path, get_trades_keyboard_layout, only_admin
from utils.msg import MSG

import time
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler, ConversationHandler, Defaults, Updater
from conversations.addtrade import AddTradeConversation
from conversations.stoptrade import StopTradeConversation
from conversations.updatetrade import UpdateTradeConversation
from conversations.adduser import AddUserConversation

from trader import Trader

# user database
db = sqlalchemy.create_engine('sqlite:///accounts.db')

class TradeBot:
    def __init__(self, config: Config):
        self.config = config
        self.is_test = config.is_test
        self.use_trailing_sl_tp = True

        # create needed folders and files
        self.init()
        
        #The percentage x% of the prime numbers 3, 5, 7, and 11 is used in the stop loss/take profit
        # calculations of the weak, strong, very strong, and extrmely strong adx respectively
        # where x is the average adx rounded to the nearest tens
        self.weak_trend = 3
        self.strong_trend = 5
        self.very_strong_trend = 7
        self.extremely_strong_trend = 11
        self.trades = {}
        self.users = {}

        self.spot_market = {}
        self.last_spot_market_update_time = 0

        self.futures_market = {}
        self.last_futures_market_update_time = 0

        defaults = Defaults(parse_mode=ParseMode.HTML, disable_web_page_preview=True, timeout=120)
        # persistence = PicklePersistence(filename='botpersistence')
        self.updater = Updater(token=config.secrets.telegram_token, persistence=None, defaults=defaults)
        self.dispatcher = self.updater.dispatcher
        self.convos = {
            'addtrade': AddTradeConversation(parent=self, config=self.config),
            'updatetrade': UpdateTradeConversation(parent=self, config=self.config),
            'stoptrade': StopTradeConversation(parent=self, config=self.config),
            'adduser': AddUserConversation(parent=self, config=self.config)
        }
        self.setup_telegram()
        #self.start_status_update()
        self.last_status_message_id: Optional[int] = None
        self.prompts_select_token = {
            'updatetrade': 'Which trade do you want to update its settings?',
            'stoptrade': 'Which trade do you want to stop?'
        }

    def init(self):
        self.client = Client(Config.Binance.key, Config.Binance.secret)
        if not os.path.isdir(Constants.chart_photos_dir_name):
            os.mkdir(Constants.chart_photos_dir_name)
        if not os.path.isdir(Constants.log_dir_name):
            os.mkdir(Constants.log_dir_name)

    def setupuser(self, update: Update):
        user_key = self.get_user_key(update)
        if user_key is not None and user_key not in self.trades:
            self.trades[user_key] = {
                Constants.TradeType.spot: {},
                Constants.TradeType.futures: {}
            }

    def get_user_key(self, update: Update):
        chat_id = update_to_chat_id(update)
        return f'chat_{chat_id}' if chat_id is not None else None 

    def get_user_key_from_id(self, chat_id: str):
        return f'chat_{chat_id}' if chat_id is not None else None 

    def get_trade_key(self, tradetype):
        return f'{tradetype}'

    def get_user_trades_by_type(self, type: str, update: Update):
        user_key = self.get_user_key(update)
        user_trades = None
        logger.info("UserTrades101")
        logger.info(self.trades)
        if user_key not in self.trades:
            user_trades = {}
        else:
            user_trades = self.trades[user_key][self.get_trade_key(type)]
        logger.info("UserTrades")
        logger.info(user_trades)
        return user_trades

    def trade_exists(self, symbol: str, trade_type: str, update: Update):
        return symbol.upper() in self.get_user_trades_by_type(trade_type, update)

    def get_trade(self, symbol: str, trade_type: str, update: Update):
        return self.get_user_trades_by_type(trade_type, update)[symbol.upper()]

    '''
    {
        "symbol": "BTCUSDT",
        "pair": "BTCUSDT",
        "contractType": "PERPETUAL",
        "deliveryDate": 4133404800000,
        "onboardDate": 1569398400000,
        "status": "TRADING",
        "maintMarginPercent": "2.5000",
        "requiredMarginPercent": "5.0000",
        "baseAsset": "BTC", # Note
        "quoteAsset": "USDT", # Note
        "marginAsset": "USDT", # Note
        "pricePrecision": 2, # Note
        "quantityPrecision": 3, # Note
        "baseAssetPrecision": 8, # Note
        "quotePrecision": 8, # Note
        ...
    }
    '''
    def update_futures_market(self):
        t_diff = time_diff_now(self.last_futures_market_update_time)
        if len(self.futures_market) == 0 or t_diff is None or t_diff.seconds > Config.market_info_update_interval_seconds:
            market = self.client.futures_exchange_info()
            for symbol in market['symbols']:
                if symbol['contractType'] == 'PERPETUAL':
                    self.futures_market[symbol['symbol']] = symbol
            self.last_futures_market_update_time = DT.datetime.now()

    '''
    {
        'symbol': 'ETHBTC',
        'status': 'TRADING',
        'baseAsset': 'ETH',
        'baseAssetPrecision': 8,
        'quoteAsset': 'BTC',
        'quotePrecision': 8,
        'quoteAssetPrecision': 8
        ...
    }
    '''
    def update_spot_market(self):
        t_diff = time_diff_now(self.last_spot_market_update_time)
        if len(self.spot_market) == 0 or t_diff is None or t_diff.seconds > Config.market_info_update_interval_seconds:
            market = self.client.get_exchange_info()
            for symbol in market['symbols']:
                self.spot_market[symbol['symbol']] = symbol
            self.last_spot_market_update_time = DT.datetime.now()

    # checks the symbol on the list of binance futures pairs, and return true if the symbol exists
    def futures_has_symbol(self, symbol):
        self.update_futures_market()

        has_it = symbol.upper() in self.futures_market
        if has_it is False:
            return False
        else:
            symbol_info = SymbolInfo.from_dict(self.futures_market[symbol.upper()])
            return self.symbol_info_allowed(symbol_info)


    # checks the symbol on the list of binance spot pairs, and return true if the symbol exists
    def spot_has_symbol(self, symbol):
        self.update_spot_market()

        has_it = symbol.upper() in self.spot_market
        if has_it is False:
            return False
        else:
            symbol_info = SymbolInfo.from_dict(self.spot_market[symbol.upper()])
            return self.symbol_info_allowed(symbol_info)

    def symbol_info_allowed(self, symbol_info: SymbolInfo):
        # market_info_update_interval_seconds = 86400 # 1 day
        # base_assets_whitelist = []
        # base_assets_blacklist = []
        # quote_assets_whitelist = ['USDT', 'BUSD']
        # quote_assets_blacklist = []
        return (
            (
            len(Config.base_assets_whitelist) == 0 or symbol_info.baseAsset in Config.base_assets_whitelist
            ) and
            (
            len(Config.base_assets_blacklist) == 0 or symbol_info.baseAsset not in Config.base_assets_blacklist
            ) and
            (
            len(Config.quote_assets_whitelist) == 0 or symbol_info.quoteAsset in Config.quote_assets_whitelist
            ) and
            (
            len(Config.quote_assets_blacklist) == 0 or symbol_info.quoteAsset not in Config.quote_assets_blacklist
            )
        )

    def setup_telegram(self):
        self.dispatcher.add_handler(CommandHandler('start', self.command_start))
        self.dispatcher.add_handler(CommandHandler('status', self.command_status))
        self.dispatcher.add_handler(CommandHandler('removeuser', self.command_removeuser))
        self.dispatcher.add_handler(CommandHandler('updatetrade', self.command_show_all_trades))
        self.dispatcher.add_handler(CommandHandler('stoptrade', self.command_show_all_trades))
        #self.dispatcher.add_handler(CommandHandler('about', self.command_about))
        #self.dispatcher.add_handler(CommandHandler('dev', self.command_dev))
        self.dispatcher.add_handler(CommandHandler('logs', self.command_logs))

        self.dispatcher.add_handler(
            CallbackQueryHandler(
                self.command_show_all_trades, pattern='^updatetrade$|^stoptrade$'
            )
        )
        self.dispatcher.add_handler(
            CallbackQueryHandler(
                self.command_restart_trade, pattern='^restart_trade:[^:]*$'
            )
        )
        self.dispatcher.add_handler(
            CallbackQueryHandler(
                self.command_removeuser_confirm, pattern='^removeuser:[^:]*$'
            )
        )
        self.dispatcher.add_handler(CallbackQueryHandler(self.cancel_command, pattern='^stoptradechoice$'))
        for convo in self.convos.values():
            self.dispatcher.add_handler(convo.handler)
        commands = [
            ('status', 'Display all trades and their PNL'),
            ('addtrade', 'Buy/Long or sell/Short an asset'),
            ('updatetrade', 'Update the settings of a trade'),
            ('stoptrade', 'Pause/Remove a trade'),
            ('cancel', 'Cancel the current operation'),
            ('adduser', 'Add a user'),
            ('removeuser', 'Remove a user'),
            #('about', 'About the bot and its workings'),
            #('dev', 'About the developer and contact'),
            ('logs', 'Get bot log files')
        ]
        self.dispatcher.bot.set_my_commands(commands=commands)
        self.dispatcher.add_error_handler(self.error_handler)
        
    def start(self):
        try:
            self.dispatcher.bot.send_message(chat_id=self.config.secrets.admin_chat_id, text='🤖 Bot started')
        except Exception:  # chat doesn't exist yet, do nothing
            logger.info('Chat with user doesn\'t exist yet.')
        logger.info('Bot started')
        self.updater.start_polling()
        self.updater.idle()

    @check_chat_id
    def command_start(self, update: Update, context: CallbackContext):
        chat_message(
            update,
            context,
            text='Hi! You can start trading futures and spot with the '
            + '<a href="/addtrade">/addtrade</a> command.',
            edit=False,
        )

    @only_admin
    def command_removeuser(self, update: Update, context: CallbackContext):
        if len(self.users.values()) == 0:
            chat_message(
                update,
                context,
                text=MSG.no_user_found,
                edit=False,
            )
        else:
            chat_message(
                update,
                context,
                text="Which user do you want to remove?",
                edit=False,
            )
            for user in self.users.values():
                chat_message(
                    update,
                    context,
                    text=f'Want to remove user with ID {user}?',
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(f'🛑 Yes Remove', callback_data=f'removeuser:{user}')
                        ]
                    ]),
                    edit=False
                )
                time.sleep(0.2)
                chat_message(
                    update,
                    context,
                    text=f'-',
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(f'Cancel', callback_data=f'stoptradechoice')
                        ]
                    ]),
                    edit=False
                )
                

    @only_admin
    def command_removeuser_confirm(self, update: Update, context: CallbackContext):
        assert update.callback_query and update.effective_chat
        query = update.callback_query
        assert query.data
        user_id = query.data.split(':')[1].strip()
        if not self.signed_up(id=user_id):
            chat_message(update, context, text='⛔️ User does not exist.', edit=False)
            return ConversationHandler.END
        
        self.removeuser(
            id=user_id,
            update=update,
            context=context
        )
        return ConversationHandler.END
                
    @check_chat_id
    def command_status(self, update: Update, context: CallbackContext):
        chat_id = update_to_chat_id(update)
        spot_trades = self.get_user_trades_by_type(Constants.TradeType.spot, update)
        futures_trades = self.get_user_trades_by_type(Constants.TradeType.futures, update)

        if len(spot_trades) == 0 and len(futures_trades) == 0:
            chat_message(
                update,
                context,
                text=MSG.no_trade_info,
                edit=False,
            )
        else:
            if len(spot_trades) > 0:
                for trader in sorted(spot_trades.values(), key=lambda trader: trader.symbol):
                    status = trader.get_status(chat_id)
                    trade_path = get_trade_path(trade_type=Constants.TradeType.spot, trade_symbol=trader.symbol)
                    reply_markup = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton('✏️ Edit Trade', callback_data=f'updatetrade:{trade_path}'),
                            InlineKeyboardButton('🛑 Stop Trade' if trader.alive else '▶ Restart Trade', callback_data=f'{"stoptrade" if trader.alive else "restart_trade"}:{trade_path}')
                        ]
                    ])
                    chat_message(
                        update,
                        context,
                        text=status,
                        reply_markup=reply_markup,
                        edit=False,
                        photo_up=trader.chart_photo_path
                    )
                    time.sleep(0.2)
            if len(futures_trades) > 0:
                for trader in sorted(futures_trades.values(), key=lambda trader: trader.symbol):
                    status = trader.get_status(chat_id)
                    trade_path = get_trade_path(trade_type=Constants.TradeType.futures, trade_symbol=trader.symbol)
                    reply_markup = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton('✏️ Edit Trade', callback_data=f'updatetrade:{trade_path}'),
                            InlineKeyboardButton('🛑 Stop Trade' if trader.alive else '▶ Restart Trade', callback_data=f'{"stoptrade" if trader.alive else "restart_trade"}:{trade_path}')
                        ]
                    ])
                    chat_message(
                        update,
                        context,
                        text=status,
                        reply_markup=reply_markup,
                        edit=False,
                        photo_up=trader.chart_photo_path
                    )
                    time.sleep(0.2)

    @check_chat_id
    def command_restart_trade(self, update: Update, context: CallbackContext):
        assert update.callback_query
        query = update.callback_query
        assert query.data
        query.delete_message()
        trade_keys = query.data.split(':')[1].split(Constants.trade_keys_separator)
        trade_type = trade_keys[0]
        trade_symbol = trade_keys[1]
        if not self.trade_exists(symbol=trade_symbol, trade_type=trade_type, update=update):
            chat_message(update, context, text='⛔️ Invalid trade.', edit=False)
            return ConversationHandler.END
        
        trader = self.get_trade(symbol=trade_symbol, trade_type=trade_type, update=update)
        trader.trade()
        self.send_feedback(update, context, trader.feedback)

    @check_chat_id
    def command_about(self, update: Update, context: CallbackContext):
        chat_message(
            update=update,
            context=context,
            photo_up=Constants.logo_filename,
            text=MSG.about,
            edit=False,
        )


    @check_chat_id
    def command_dev(self, update: Update, context: CallbackContext):
        chat_message(
            update=update,
            context=context,
            photo_up=Constants.dev_logo_filename,
            text=MSG.dev,
            edit=False,
        )

    @only_admin
    def command_logs(self, update: Update, context: CallbackContext):
        chat_message(
            update=update,
            context=context,
            text=MSG.log_files,
            edit=False,
            docs=[
                f'{Constants.log_dir_name}/{Constants.info_log_filename}', 
                f'{Constants.log_dir_name}/{Constants.warning_log_filename}', 
                f'{Constants.log_dir_name}/{Constants.error_log_filename}', 
                f'{Constants.log_dir_name}/{Constants.pos_log_filename}', 
                f'{Constants.log_dir_name}/{Constants.chart_log_db_filename}',
            ]
        )

    @check_chat_id
    def command_show_all_trades(self, update: Update, context: CallbackContext):
        if update.message: # process text command such as /stoptrade, /updatetrade... from user
            assert update.message.text
            command = update.message.text.strip()[1:] # e.g turns /stoptrade to stoptrade
            try:
                # get the message to display before the trades buttons
                msg = self.prompts_select_token[command]
            except KeyError:
                chat_message(update, context, text='⛔️ Invalid command.', edit=False)
                return
            buttons_layout = get_trades_keyboard_layout(
                self.get_user_trades_by_type(Constants.TradeType.spot, update), 
                self.get_user_trades_by_type(Constants.TradeType.futures, update), 
                callback_prefix=command,
                order_by='symbol'
            )
        else:  # callback query from button
            assert update.callback_query
            query = update.callback_query
            assert query.data
            try:
                msg = self.prompts_select_token[query.data]
            except KeyError:
                chat_message(update, context, text='⛔️ Invalid command.', edit=False)
                return
            buttons_layout = get_trades_keyboard_layout(
                self.get_user_trades_by_type(Constants.TradeType.spot, update), 
                self.get_user_trades_by_type(Constants.TradeType.futures, update), 
                callback_prefix=query.data,
                order_by='symbol'
            )

        if len(buttons_layout) == 0:
            chat_message(
                update,
                context,
                text=MSG.no_trade_info,
                edit=False,
            )
            return ConversationHandler.END
        else:
            reply_markup = InlineKeyboardMarkup(buttons_layout)
            chat_message(
                update,
                context,
                text=msg,
                reply_markup=reply_markup,
                edit=False,
            )

    @check_chat_id
    def cancel_command(self, update: Update, _: CallbackContext):
        assert update.callback_query and update.effective_chat
        query = update.callback_query
        query.delete_message()


    def send_feedback(self, update: Update, context: CallbackContext, msg):
        chat_message(
            update,
            context,
            text=msg,
            edit=False
        )

    def get_symbol_info(self, symbol: str, is_futures: bool):
        symbol_dict = (self.futures_market if is_futures else self.spot_market)[symbol.upper()]
        return SymbolInfo.from_dict(symbol_dict)

    def addtrade(self, api_key: str, api_secret: str, symbol: str, margin_pct: float, leverage: int, update: Update, context: CallbackContext):
        try:
            trader = Trader(
                self,
                api_key, api_secret,
                symbol,
                self.use_trailing_sl_tp, 
                self.weak_trend, self.strong_trend, self.very_strong_trend, self.extremely_strong_trend,
                margin_pct, leverage
            )
            if trader is not None:
                self.trades[self.get_user_key(update)][Constants.TradeType.futures][symbol.upper()] = trader
            logger.info(self.trades)
            trader.trade()
            self.send_feedback(update, context, trader.feedback)
        except Exception as e:
            context.error = e
            self.error_handler(update, context)

    def updatetrade(self, symbol: str, is_futures: bool, margin_pct: float, leverage: int, use_order_book: bool, update: Update, context: CallbackContext):
        trade_type = Constants.TradeType.futures if is_futures else Constants.TradeType.spot
        trader = self.get_trade(symbol=symbol, trade_type=trade_type, update=update)
        trader.update(
            margin_pct=margin_pct, leverage=leverage, use_order_book=use_order_book
        )
        self.send_feedback(update, context, trader.feedback)

    def stoptrade(self, symbol: str, trade_type: str, delete: bool, update: Update, context: CallbackContext):
        trader = self.get_trade(symbol=symbol, trade_type=trade_type, update=update)
        trader.stop()
        if delete:
            del self.trades[self.get_user_key(update)][trade_type][symbol]
        logger.info(self.trades)
        self.send_feedback(update, context, trader.feedback)

    def error_handler(self, update: Update, context: CallbackContext) -> None:
        logger.error('Exception while handling an update')
        logger.error(context.error)
        chat_message(update, context, text=f'⛔️ Error while handling an update\n\n <b>Error:</b> {context.error}\n\n Try Again!', edit=False)

    def adduser(self, id: str, key: str, secret: str, update: Update, context: CallbackContext):
        self.users[self.get_user_key_from_id(id)] = {
            'id': id,
            'key': key,
            'secret': secret
        }
        chat_message(update, context, text=f'✅ {id} added.', edit=False)

    def getuser(self, id: str):
        if id == Config.secrets.admin_chat_id:
            return {
                'id': id,
                'key': Config.Binance.key,
                'secret': Config.Binance.secret
            }
        else:
            user_key = self.get_user_key_from_id(id)
            return None if user_key not in self.users else self.users[user_key]

    def removeuser(self, id: str, update: Update, context: CallbackContext):
        user_key = self.get_user_key_from_id(id)
        if user_key in self.trades:
            for trade in self.trades[user_key][Constants.TradeType.futures].values():
                trade.stop()
            for trade in self.trades[user_key][Constants.TradeType.spot].values():
                trade.stop()
            del self.trades[user_key]
        del self.users[id]
        chat_message(update, context, text=f'✅ {id} Removed.', edit=False)

    def signed_up(self, id):
        return self.get_user_key_from_id(id) in self.users