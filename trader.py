import time
import threading
import uuid
import os
from loguru import logger
import pandas as pd
import numpy as np
import plotly.express as px
from binance.client import Client
from binance.enums import HistoricalKlinesType
import plotly.express as px
from position import Position
from utils.config import Config

from utils.constants import Constants
from utils.core import is_admin
from utils.trade_logger import filelog, chartlog
from utils.indicators import get_adx, get_atr, get_mfi, get_rsi, get_supertrend, get_vwap
from utils.math import add, op_values_at_index, roundup
from traderstatus import TraderStatus
from utils.wallet import is_valid_wallet_address

indicator_period = 10
indicator_factor = 3

class Trader:

    def __init__(
        self, parent,
        api_key, api_secret,
        symbol,
        use_trailing_sl_tp, 
        tp_sl_ratio_weak, 
        tp_sl_ratio_strong,
        tp_sl_ratio_very_strong,
        tp_sl_ratio_extremely_strong, 
        margin_pct, leverage
    ):
        self.parent = parent
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol.upper()
        self.client = Client(api_key=self.api_key, api_secret=self.api_secret, testnet=True)
        self.use_trailing_sl_tp = use_trailing_sl_tp
        self.tp_sl_ratio_weak = tp_sl_ratio_weak
        self.tp_sl_ratio_strong = tp_sl_ratio_strong
        self.tp_sl_ratio_very_strong = tp_sl_ratio_very_strong
        self.tp_sl_ratio_extremely_strong = tp_sl_ratio_extremely_strong
        self.margin_pct = margin_pct
        self.leverage = leverage
        self.name = f'{self.symbol} {(Constants.TradeType.futures).capitalize()}'
        
        self.klines_type = HistoricalKlinesType.FUTURES

        self.balance = 50
        self.pnl = 50 # balance + profits
        self.total_longs = 0
        self.total_shorts =  0
        self.total_trades = 0
        self.avg_trend_strength = 0
        self.status = None # waiting for optimum position | trading | stopped
        self.test_counter = 0
        self.feedback = None
        self.alive = False
        self.thread = None

        self.chart_photo_path = None
        self.positions = []

        # logs for all strategies
        self.close = 0
        self.adx = 0
        self.vwap = 0

        # logs for order supertrend strategy
        self.supertrend_is_uptrend = 0
        self.supertrend_vwc = 0
        self.supertrend_trend = 0
        
        self.first_trade_time = None
        self.last_trade_time = None

        self.current_position = None
        self.last_position = None

        self.current_price = 0
        self.run_counts = 0

    # calulate the volume of an unstable coin an amount of stable coin can buy
    # e.g, the volume/size of ETH a particular amount of BUSD can buy
    def amount_to_volume(self, amount, volume_price):
        return amount * volume_price

    def build_key_value(self, key, value, hide=False, admin_only=None):
        return '' if hide else f'<b>{key}:</b> {value if value is not None else ""}\n' if admin_only is None or is_admin(admin_only) else ''

    def current_position_text(self):
        if self.current_position is None:
            return '<b>No Position Opened Yet! Bot probably waiting for an optimum position</b>\n'
        else:
            return f"{self.build_key_value('Volume/Size', f'{round(self.current_position.volume, 4)} {self.get_symbol().baseAsset}')}\
        {self.build_key_value('Type', 'LONG' if self.current_position.order_type == 'buy' else 'SHORT')}\
        {self.build_key_value('Position Amount', round(self.current_position.amount, 2))}\
        {self.build_key_value('Entry Time', self.current_position.entry_time if self.current_position.entry_time is None else self.current_position.entry_time.strftime(Config.time_format))}\
        {self.build_key_value('Entry Price', round(self.current_position.entry_price, 2))}\
        {self.build_key_value('Mark Price', round(self.current_position.mark_price, 2))}\
        {self.build_key_value('Liquidation Price', round(self.current_position.liq_price, 2))}\
        {self.build_key_value('Leverage', f'{round(self.current_position.leverage, 2)}x')}\
        {self.build_key_value('Unrealised Profit', round(self.current_position.unrealised_profit, 2))}\
        {self.build_key_value('Isolated Margin', round(self.current_position.isolated_margin, 2))}\
        {self.build_key_value('Isolated Wallet', round(self.current_position.isolated_wallet, 2))}\
        {self.build_key_value('Notional', round(self.current_position.notional, 2))}\
        {self.build_key_value('Max Notional', round(self.current_position.max_notional, 2))}\
        {self.build_key_value('Margin Type', '' if self.current_position.margin_type is None else self.current_position.margin_type)}\
        {self.build_key_value('Current TP', round(self.current_position.tp, 2))}\
        {self.build_key_value('Current SL', round(self.current_position.sl, 2))}\
        {self.build_key_value('Current TP Temp', round(self.current_position.tp_temp, 2))}\
        {self.build_key_value('Current SL Temp', round(self.current_position.sl_temp, 2))}\
            "
    def last_position_text(self):
        if self.last_position is None:
            return '<b>No Position Opened Yet! Bot probably waiting for an optimum position</b>\n' if self.current_position is None else '<b>No Position Closed Yet! Bot is still trading its first position.</b>\n'
        else:
            return f"{self.build_key_value('Volume/Size', f'{round(self.last_position.volume, 4)} {self.get_symbol().baseAsset}')}\
        {self.build_key_value('Type', 'LONG' if self.last_position.order_type == 'buy' else 'SHORT')}\
        {self.build_key_value('Position Amount', round(self.last_position.amount, 2))}\
        {self.build_key_value('Entry Time', self.last_position.entry_time if self.last_position.entry_time is None else self.last_position.entry_time.strftime(Config.time_format))}\
        {self.build_key_value('Entry Price', round(self.last_position.entry_price, 2))}\
        {self.build_key_value('Exit Time', self.last_position.exit_time if self.last_position.exit_time is None else self.last_position.exit_time.strftime(Config.time_format))}\
        {self.build_key_value('Exit Price', round(self.last_position.exit_price, 2))}\
        {self.build_key_value('Mark Price', round(self.last_position.mark_price, 2))}\
        {self.build_key_value('Liquidation Price', round(self.last_position.liq_price, 2))}\
        {self.build_key_value('Leverage', f'{round(self.last_position.leverage, 2)}x')}\
        {self.build_key_value('Unrealised Profit Before', round(self.last_position.unrealised_profit, 2))}\
        {self.build_key_value('Realised Profit', round(self.last_position.profit, 2))}\
        {self.build_key_value('Isolated Margin', round(self.last_position.isolated_margin, 2))}\
        {self.build_key_value('Isolated Wallet', round(self.last_position.isolated_wallet, 2))}\
        {self.build_key_value('Notional', round(self.last_position.notional, 2))}\
        {self.build_key_value('Max Notional', round(self.last_position.max_notional, 2))}\
        {self.build_key_value('Margin Type', '' if self.last_position.margin_type is None else self.last_position.margin_type)}\
        {self.build_key_value('Last TP', round(self.last_position.tp, 2))}\
        {self.build_key_value('Last SL', round(self.last_position.sl, 2))}\
        {self.build_key_value('Last TP Temp', round(self.last_position.tp_temp, 2))}\
        {self.build_key_value('Last SL Temp', round(self.last_position.sl_temp, 2))}\
            "
    
    def get_status(self, caller_id):
        return f"\
        === <b>{self.name} | {round(self.current_price, 2)}</b> ===\n\
        {self.build_key_value('AlgoRunCount', self.run_counts)}\
        {self.build_key_value('Status', self.status)}\
        {self.build_key_value('PNL', round(self.pnl, 2))}\n\
        {self.build_key_value('', '=== <b>General Info</b> ===<b>:</b>')}\
        {self.build_key_value('Total Longs', self.total_longs)}\
        {self.build_key_value('Total Shorts', self.total_shorts)}\
        {self.build_key_value('Total Trades', self.total_trades)}\
        {self.build_key_value('Margin', f'{self.margin_pct}%')}\
        {self.build_key_value('Leverage', f'{round(self.leverage, 2)}x')}\
        {self.build_key_value('First Trade Time', self.first_trade_time if self.first_trade_time is None else self.first_trade_time.strftime(Config.time_format))}\
        {self.build_key_value('Last Trade Time', self.last_trade_time if self.last_trade_time is None else self.last_trade_time.strftime(Config.time_format))}\
        {self.build_key_value('', '=== <b>16hrs Trend Info</b> ===<b>:</b>')}\
        {self.build_key_value('Avg. Trend Strength', f'{round(self.avg_trend_strength, 2)}%')}\n\
        {self.build_key_value('', '=== <b>Current Position Info</b> ===<b>:</b>')}\
        {self.current_position_text()}\n\
        {self.build_key_value('', '=== <b>Last Position Info</b> ===<b>:</b>')}\
        {self.last_position_text()}\n\
        {self.build_key_value('', '=== <b>Dev Logs</b> ===<b>:</b>')}\
        {self.build_key_value('close', round(self.close, 2))}\
        {self.build_key_value('adx', round(self.adx, 2))}\
        {self.build_key_value('vwap', round(self.vwap, 2))}\
        {self.build_key_value('supertrend_is_uptrend', self.supertrend_is_uptrend)}\
        {self.build_key_value('supertrend_vwc', round(self.supertrend_vwc, 2))}\
        {self.build_key_value('supertrend_trend', round(self.supertrend_trend, 2))}\
    "

    def get_current_price(self):
        # return float(self.client.futures_mark_price(symbol=self.symbol)['markPrice'])
        return float(self.client.futures_symbol_ticker(symbol=self.symbol)['price'])

    def get_symbol(self):
        return self.parent.get_symbol_info(symbol=self.symbol, is_futures=True)

    def update_balance(self):
        balances = self.client.futures_account_balance()
        balance_key = 'balance'
        for balance in balances:
            symbol_info = self.get_symbol()
            if balance['asset'] == symbol_info.quoteAsset:
                self.balance = float(balance[balance_key])
                self.pnl = self.balance
                break

    def update_current_position_info(self):
        current_position = self.get_open_position()
        if current_position is not None:
            info = self.client.futures_position_information(symbol=self.symbol)
            if info is not None and len(info) > 0:
                info = self.dict_to_object(info[0])
                # if the entry price is not greater than zero, it means there's no position opened yet
                if float(info.entryPrice) > 0:
                    current_position.amount = float(info.positionAmt)
                    current_position.entry_price = float(info.entryPrice)
                    current_position.mark_price = float(info.markPrice)
                    current_position.liq_price = float(info.liquidationPrice)
                    current_position.leverage = float(info.leverage)
                    current_position.unrealised_profit = float(info.unRealizedProfit)
                    current_position.isolated_margin = float(info.isolatedMargin)
                    current_position.isolated_wallet = float(info.isolatedWallet)
                    current_position.notional = float(info.notional)
                    current_position.max_notional = float(info.maxNotionalValue)
                    current_position.margin_type = info.marginType
                    self.current_position = current_position       

    def run_trade(self):
        self.update_settings_on_exchange()
        while self.alive:
            try:
                self.run_counts = self.run_counts + 1
                
                # get the latest account balance so that the bot can calculate 
                # a percentage of it for the next trade
                #if self.get_open_position() is None:
                self.update_balance()

                # update the current position info
                self.update_current_position_info()

                # set the current price
                self.current_price = self.get_current_price()

                # get historical data to for the bot to strategize on    
                klines = self.client.get_historical_klines(
                    self.symbol, 
                    Config.timeframe, 
                    limit=Config.max_positions_per_chart, 
                    klines_type=self.klines_type
                )
                if klines is not None:
                    # transfrom the data to panda dataframe
                    df = self.klines_to_dataframe(klines)
                    
                    # send the dataframe to the bot to react on 
                    df = self.react(df)
                    # log the chart dataframe for later debugging or bot improvement
                    chartlog(df)
                    try:
                        # create a picture of the latest chart with profits and loss points marked
                        self.update_chart_photo(df)
                    except Exception as e:
                        logger.warning(f'ChartPhotoError: {e}')
                # check the states of the position, take profit, and stop loss orders made when the 
                # bot reacted to the chart and make decisions based on the states
                self.check_orders()
                time.sleep(Config.fetch_interval_seconds)
                    
            except Exception as e:
                self.handle_error(e)

    def handle_error(self, e):
        #APIError(code=-4129): Time in Force (TIF) GTE can only be used 
        # with open positions or open orders. Please ensure 
        # that open orders or positions are available.
        if 'apierror(code=-4129)' in str(e).lower():
            # this means the user has closed the trade outside of the bot
            # this may happen if the user panicked
            # the user could have also tried to game the bot fee by manually closing on profit
            ok = True
        # urllib3 HTTPError ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
        elif 'connection' in str(e).lower():
            ok = True
        else:
            try:
                self.stop(str(e))
            except Exception as e:
                self.handle_close_error(e)
        logger.error(f'TraderError: {e}')

    def handle_close_error(self, e):
        #APIError(code=-4129): Time in Force (TIF) GTE can only be used 
        # with open positions or open orders. Please ensure 
        # that open orders or positions are available.
        if 'apierror(code=-4129)' in str(e).lower():
            # this means the user has closed the trade outside of the bot
            # this may happen if the user panicked
            # the user could have also tried to game the bot fee by manually closing on profit
            ok = True
        # urllib3 HTTPError ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
        elif 'connection' in str(e).lower():
            ok = True
        else:
            notok = True
        logger.error(f'TraderError: {e}')


    def trade(self):
        self.alive = True
        self.status = TraderStatus.waiting
        self.thread = threading.Thread(target = self.run_trade)
        self.thread.start()
        self.feedback = f'✅ <b>{self.name}</b> trade was successfully started for execution once the time is right. \n\nYou can update the settings with the <a href="/{Constants.Commands.updatetrade}">/{Constants.Commands.updatetrade}</a> command. \n\nYou can also cancel it with the <a href="/{Constants.Commands.removetrade}">/{Constants.Commands.removetrade}</a> command. \n\nTo view the status of your trades like checking if a trade has been executed, use the <a href="/{Constants.Commands.status}">/{Constants.Commands.status}</a> command.'
        
    def update(self, margin_pct, leverage, use_order_book):
        self.margin_pct = margin_pct
        self.leverage = leverage
        self.use_order_book = use_order_book
        self.update_settings_on_exchange()

        self.total_ob_fetches = 0
        self.total_bids_volume = 0
        self.total_asks_volume = 0
        self.best_bids_volume = 0
        self.best_asks_volume = 0
        self.best_bids_price = 0
        self.best_asks_price = 0

        self.feedback = f'✅ <b>{self.name}</b> trade was successfully updated. The trading bot will start using the settings on the next trade action.'

    def update_settings_on_exchange(self):
        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
        except Exception as e:
            logger.warning(f'update_settings_on_exchange:leverage {e}')

        try:
            self.client.futures_change_margin_type(symbol=self.symbol, marginType='ISOLATED')
        except Exception as e:
            logger.warning(f'update_settings_on_exchange:margin_type {e}')

    def stop(self, msg=None):
        self.alive = False
        self.status = msg if msg is not None else TraderStatus.stopped
        self.react(df=None)
        try:
            self.thread.join()
        except Exception as e:
            filelog(
                f'{Constants.log_dir_name}/{Constants.error_log_filename}', str(e) + Constants.log_text_nl
            )
        symbol_info = self.parent.get_symbol_info(self.symbol, True)
        self.feedback = msg if msg is not None else f'✅ <b>{self.name}</b> trade was successfully stopped with all {symbol_info.baseAsset} sold into the {symbol_info.quoteAsset} stable coin at market price.'

    def get_positions_df(self):
        df = pd.DataFrame([position.asdict() for position in self.positions])
        return df

    def get_open_position(self):
        last_position = self.get_last_position()
        return last_position if last_position is not None and last_position.is_closed is False else None

    def dict_to_object(self, dict):
        dict = pd.DataFrame([dict])
        return dict.iloc[0]

    def order_to_df(self, order):
        order = pd.DataFrame([order])
        order.time = pd.to_datetime(order.time, unit='ms')
        order.updateTime = pd.to_datetime(order.updateTime, unit='ms')
        order.avgPrice = float(order.avgPrice)
        return order.iloc[0]

    # log the closed position into the database and take bot's fee from user's profit
    def on_postion_closed(self, position):
        ## reset the current position and update the last position ##
        self.current_position = None
        self.last_position = position
        # update the trade status
        self.status = TraderStatus.waiting
        # log the closed position into the database
        # -- log code here --
        # take bot's fee from user's profit
        if position.profit > 0 and Config.bot_fee_profit_percentage > 0 and is_valid_wallet_address(Config.bot_fee_profit_destination):
            fee = (position.profit * Config.bot_fee_profit_percentage) / 100
            # check if fee is greater than minimum withdrawn.
            # if greater or equal, withdraw the fee to the destination. 
            # if less save the fee as the amount the user is owing the bot and deduct 
            # it from the pnl before calulating trades volume in the future.
            # Also notify the users of the bot fee owned on there status
            code_to_be_continued = True

    # the current and last positions are updated here when position order status is filled
    # and when tp or sl order is filled respectively
    def check_orders(self):
        # get the last position if it hasn't been closed yet
        last_position = self.get_open_position()
        # if the last postion order has not fiiled or an order to take profit or stop loss on last postion was already sent to the exchange
        if last_position is not None and (last_position.orderFilled is False or last_position.tpOrderId is not None or last_position.slOrderId is not None):
            #check if the order has filled
            orders = self.client.futures_get_open_orders(symbol=self.symbol)
            # if the order has filled here before getting to the code block that checks and 
            # log the order state, this means we have confirmed the filling previously,
            # and so it means we have initialised the position previously too, since 
            # initialisation occurs after the order has been confirmed to be filled. 
            # A confirmation which is done in the code block below through open orders iteration
            hasInitialisedPosition = last_position.orderFilled
            orderFilled = True
            has_tp = True if last_position.tpOrderId is not None else False
            has_sl = True if last_position.slOrderId is not None else False
            # any order, be it position order(orderId), TP order(tpOrderId), SL order(slOrderId), that 
            # is present in the open orders iterated below is obviously not filled. 
            # So ones not present are filled
            for order in orders:
                if order['orderId'] == last_position.orderId:
                    orderFilled = False # The position order is yet to be filled
                elif order['orderId'] == last_position.tpOrderId:
                    has_tp = False # The take profit order is yet to be filled 
                elif order['orderId'] == last_position.slOrderId:
                    has_sl = False # The stop loss order is yet to be filled
            # log if the order has filled or not from the above iteration result
            last_position.orderFilled = orderFilled

            # check the position order and update the entry_price and entry_time if it has filled
            # but if it has expired, remove the position since there's nothing being traded
            if orderFilled and hasInitialisedPosition is False:
                posOrder = self.client.futures_get_order(symbol=self.symbol, orderId=last_position.orderId)
                if posOrder is not None:
                    posOrder = self.order_to_df(posOrder)
                    if posOrder.status == 'FILLED':
                        # update the order entry price and time
                        last_position.entry_price = posOrder.avgPrice
                        last_position.entry_time = posOrder.updateTime
                        # update the "take profit" and "stop loss" mark of the trade position
                        last_position.update_tp_sl()
                        # reset the first and last trade time
                        if self.first_trade_time is None:
                            self.first_trade_time = last_position.entry_time
                        self.last_trade_time = last_position.entry_time
                        # reset total counts for longs, shorts, and all trades in general
                        if last_position.order_type == 'buy': 
                            self.total_longs = self.total_longs + 1
                        else:
                            self.total_shorts = self.total_shorts + 1
                        self.total_trades = self.total_trades + 1
                        ## update the current position ##
                        self.current_position = last_position
                    elif posOrder.status == 'EXPIRED':
                        # remove the order
                        self.positions = self.positions[0:len(self.positions) - 1]
            else:
                last_position.is_closed = has_tp or has_sl
                # if the opened position has closed by take profit(tp) or stop losss(sl), 
                # get the close time and close price from the condition that triggered the close 
                # and update the position with the close price and close time
                if last_position.is_closed:
                    closeOrder = None
                    if has_tp:
                        tpOrder = self.client.futures_get_order(symbol=self.symbol, orderId=last_position.tpOrderId)
                        if tpOrder is not None and tpOrder['status'] == 'FILLED':
                            closeOrder = self.order_to_df(tpOrder) # tp was hit
                    if has_sl and closeOrder is None: # tp wasn't hit, so check sl has
                        slOrder = self.client.futures_get_order(symbol=self.symbol, orderId=last_position.slOrderId)
                        if slOrder is not None and slOrder['status'] == 'FILLED':
                            closeOrder = self.order_to_df(slOrder) # sl was hit
                    if closeOrder is not None: # tp or sl was hit
                        # update the position close price and time so the chart 
                        # and profit calculator can use them
                        last_position.exit_price = closeOrder.avgPrice
                        last_position.exit_time = closeOrder.updateTime
                        last_position.update_profit()
                        self.on_postion_closed(last_position)
                    else:
                        # If we got here..., that's wierd and bad. 
                        # It means both the tp and sl order canceled or expired.
                        # We should definetly clear the tp and sl order IDs 
                        # so the bot can send another tp or sl order to the exchange
                        last_position.tpOrderId = None
                        last_position.slOrderId = None
                        last_position.tpClientOrderId = None
                        last_position.slClientOrderId = None
                        last_position.is_closed = False

            logger.info('--check_orders:last_position:--')
            logger.info(last_position.asdict())
            logger.info('--check_orders:orders:--')
            logger.info(orders)
            filelog(
                f'{Constants.log_dir_name}/{Constants.info_log_filename}', 
                '--check_orders--\n' +
                f'last_position: {last_position.asdict()}\n' + 
                f'{str(orders)}' + 
                Constants.log_text_nl
            )


    def add_position(self, position):
        if position.volume > 0:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='BUY' if position.order_type == 'buy' else 'SELL',
                #positionSide='LONG' if position.order_type == 'buy' else 'SHORT',
                type='MARKET',# MARKET || LIMIT
                quantity=position.volume,
                #price=position.entry_price,
                #timeInForce='IOC'#GTC (Good-Till-Cancel) || IOC (Immediate-Or-Cancel) || FOK (Fill-Or-Kill)
            )
            position.orderId = order['orderId']
            position.clientOrderId = order['clientOrderId']
            logger.info('Trade::OpenOrder:')
            logger.info(position.asdict())
            filelog(
                f'{Constants.log_dir_name}/{Constants.info_log_filename}', 
                '--add_position--\n' +
                f'position: {position.asdict()}' + 
                Constants.log_text_nl
            )

            self.positions.append(position)
            # remove the oldest position if the total postions has exceeded the limit size
            if len(self.positions) > Config.max_positions_per_chart:
                self.positions = self.positions[len(self.positions) - Config.max_positions_per_chart:]

    def take_profit(self, position):
        if position.tpOrderId is None:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='SELL' if position.order_type == 'buy' else 'BUY',
                type='TAKE_PROFIT_MARKET',
                #positionSide='LONG' if position.order_type == 'buy' else 'SHORT',
                quantity=position.volume,
                stopPrice=position.tp if position.tp_temp == 0 else position.tp_temp,
                closePosition=True,
                timeInForce='GTE_GTC',
                #reduceOnly=True
            )
            position.tpOrderId = order['orderId']
            position.tpClientOrderId = order['clientOrderId']
            logger.info('Trade::CloseOrder:TP')
            logger.info(position.asdict())
            filelog(
                f'{Constants.log_dir_name}/{Constants.info_log_filename}', 
                '--take_profit--\n' +
                f'position: {position.asdict()}' + 
                Constants.log_text_nl
            )

    def stop_loss(self, position):
        if position.slOrderId is None:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='SELL' if position.order_type == 'buy' else 'BUY',
                type='STOP_MARKET',
                #positionSide='LONG' if position.order_type == 'buy' else 'SHORT',
                quantity=position.volume,
                stopPrice=position.sl if position.sl_temp == 0 else position.sl_temp,
                closePosition=True,
                timeInForce='GTE_GTC',
                #reduceOnly=True
            )
            position.slOrderId = order['orderId']
            position.slClientOrderId = order['clientOrderId']
            logger.info('Trade::CloseOrder:SL')
            logger.info(position.asdict())
            filelog(
                f'{Constants.log_dir_name}/{Constants.info_log_filename}', 
                '--stop_loss--\n' +
                f'position: {position.asdict()}' + 
                Constants.log_text_nl
            )

    def get_last_position(self):
        return self.positions[len(self.positions) - 1] if len(self.positions) > 0 else None

    def update_chart_photo(self, chart_df):
        fig = px.line(chart_df, x='time', y=['close', 'vwap'], title=f'{Config.bot_name} {self.name} Quantitatively Analysed {Config.timeframe} Chart.')
        
        oldest_tick = chart_df.iloc[0]
        trades_df = self.get_positions_df()
        for i, position in trades_df.iterrows():
            if position.is_closed and position.exit_time is not None and position.exit_time >= oldest_tick.time:
                fig.add_shape(type="line",
                    x0=position.entry_time, y0=position.entry_price, x1=position.exit_time, y1=position.exit_price,
                    line=dict(
                        color = "green" if position.profit >= 0 else "red",
                        width = 3
                    )
                )
        photo_path = self.save_chart_photo(fig)
        if photo_path is not None:
            # delete previous photo then assign a new one
            if self.chart_photo_path is not None and os.path.isfile(self.chart_photo_path):
                os.remove(self.chart_photo_path)
            self.chart_photo_path = photo_path

    def save_chart_photo(self, fig):
        filename = f'{Constants.chart_photos_dir_name}/{str(uuid.uuid4())}.png'
        try:
            fig.write_image(filename)
            return filename
        except:
            return None


    def klines_to_dataframe(self, klines):
        df = pd.DataFrame(np.array(klines).reshape(-1,12), dtype=float, columns = ('open_time',
                                            'open',
                                            'high',
                                            'low',
                                            'close',
                                            'volume',
                                            'close_time',#close time
                                            'quote_asset_volume',
                                            'number_of_trades',
                                            'taker_buy_base_asset_volume',
                                            'taker_buy_quote_asset_volume',
                                            'ignore'))
        
        df = pd.DataFrame({
            'time': df['close_time'],
            'open': df['open'],
            'high': df['high'],
            'low': df['low'],
            'close': df['close'],
            'volume': df['volume']
        })
        
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.index = df.time
        return df


    def react(self, df: pd.DataFrame):
        if df is None:
            # this means the bots has stopped, so all trades should be closed
            pos = self.get_last_position()
            if pos and not pos.is_closed:
                pos.close_position()
            return None
        else:
            atr_indicator = get_atr(df['high'], df['low'], indicator_period)
            adx_indicator = get_adx(df['high'], df['low'], atr_indicator['atr'])
            rsi_indicator = get_rsi(df['open'], df['close'], indicator_period)
            mfi_indicator = get_mfi(df['close'], df['high'], df['low'], df['volume'], indicator_period)
            supertrend = get_supertrend(
                high=df['high'], 
                low=df['low'], 
                close=df['close'], 
                volume=df['volume'], 
                atr_period=indicator_period,
                multiplier=indicator_factor
            )
            vwap_indicator = get_vwap(
                high=df['high'], 
                low=df['low'], 
                close=df['close'], 
                volume=df['volume']
            )
            df['atr'] = atr_indicator['atr']
            df['adx'] = adx_indicator['adx']
            df['rsi'] = rsi_indicator['rsi']
            df['mfi'] = mfi_indicator['mfi']
            df['supertrend_is_uptrend'] = supertrend['supertrend_is_uptrend']
            df['supertrend_trend'] = supertrend['supertrend']
            df['supertrend_vwc'] = supertrend['volume_weighted_close']
            df['vwap'] = vwap_indicator['vwap']
            strategy_feed = df[indicator_period:]  # removing NaN values
            self.strategize(strategy_feed)
            return df

    def strategize(self, feed):
        self.avg_trend_strength = feed['adx'].sum() / feed['adx'].size
        adx_avg = roundup(self.avg_trend_strength, 10)
        data = feed.iloc[feed['adx'].size - 1]
        new_pos = self.logic(data, adx_avg)
        logger.info(f"Position::Q, {'None' if new_pos is None else new_pos.asdict()}")
        self.close_tp_sl(data=data, new_pos=new_pos)
        self.check_to_add_position(new_pos)       

    def check_to_add_position(self, new_pos):
        last_position = self.get_last_position()
        # strategy logic
        # trade only if a position is not already opened up
        # trade only if there is a signal returned to be traded(indicated by "new_pos")
        # trade only buy signals, unless this trader instance only trades futures, 
        # in which profits can be made in sell(shorts) actions too... yummy
        if (last_position is None or last_position.is_closed) \
            and new_pos is not None and new_pos.volume > 0:
            logger.info(f"Position::R', {new_pos.asdict()}")
            self.status = TraderStatus.trading
            self.add_position(new_pos)

    # close positions when stop loss or take profit is reached
    def close_tp_sl(self, data, new_pos):
        pos = self.get_last_position()
        if pos and not pos.is_closed:
            if (float(data['close']) <= float(pos.sl) and pos.order_type == 'buy'):
                pos.close_position(Position.SL, data['close'])
            elif (float(data['close']) >= float(pos.sl) and pos.order_type == 'sell'):
                pos.close_position(Position.SL, data['close'])
            elif (float(data['close']) >= float(pos.tp) and pos.order_type == 'buy'):
                # trailing tp and sl
                if new_pos is not None and new_pos.order_type == pos.order_type and self.use_trailing_sl_tp:
                    pos.tp = new_pos.tp
                    pos.sl = new_pos.sl
                    pos.tp_sl_rate = new_pos.tp_sl_rate
                elif new_pos is not None or not self.use_trailing_sl_tp:# don't close yet in an indecisicve market
                    pos.close_position(Position.TP, data['close'])
            elif (float(data['close']) <= float(pos.tp) and pos.order_type == 'sell'):
                # trailing tp and sl
                if new_pos is not None and new_pos.order_type == pos.order_type and self.use_trailing_sl_tp:
                    pos.tp = new_pos.tp
                    pos.sl = new_pos.sl
                    pos.tp_sl_rate = new_pos.tp_sl_rate
                elif new_pos is not None or not self.use_trailing_sl_tp:# don't close yet in an indecisicve market
                    pos.close_position(Position.TP, data['close'])

    def sl_tp_diff(self, atr, adx, adx_avg):
        return 1.1 * atr
        ratio = None
        if adx < 20:
            ratio = (adx_avg * self.tp_sl_ratio_weak) / 100
        elif adx < 50:
            ratio = (adx_avg * self.tp_sl_ratio_strong) / 100
        elif adx < 70:
            ratio = (adx_avg * self.tp_sl_ratio_very_strong) / 100
        else:
            ratio = (adx_avg * self.tp_sl_ratio_extremely_strong) / 100
        return ratio * atr

    def calculate_volume(self, price_per_volume):
        # Initial Margin = Quantity X EntryPrice X IMR
        # IMR = 1 / Leverage
        margin = (self.margin_pct * self.pnl) / 100
        # calculate the quantity the leverage will get
        qty = (margin * self.leverage) / price_per_volume
        info = self.parent.get_symbol_info(self.symbol, True)
        precision = int(info.quantityPrecision)
        return float("{:0.0{}f}".format(qty, precision))

    def get_precise_price(self, price):
        info = self.parent.get_symbol_info(self.symbol, True)
        precision = int(info.pricePrecision)
        return float("{:0.0{}f}".format(price, precision))
        
    # strategy logic how positions should be opened/closed
    def logic(self, data, adx_avg) -> Position:
        pos = None
        self.close = data['close']
        self.adx = data['adx']
        self.vwap = data['vwap']
        self.supertrend_is_uptrend = data['supertrend_is_uptrend']
        self.supertrend_vwc = data['supertrend_vwc']
        self.supertrend_trend = data['supertrend_trend']
        
        if data['adx'] >= 15:
            # USE SUPERTREND INDICATOR TO MAKE A STRATEGY
            # supertrend is uptrend
            # close > supertrend
            # close > vwap
            if bool(data['supertrend_is_uptrend']) is True:# \
                #and data['supertrend_vwc'] > data['supertrend_trend'] \
                #and data['close'] > data['vwap']:
                logger.info('PriceAction::LONG')
                # Position variables
                order_type = 'buy'
                entry_price = data['close']
                entry_time = data['time']
                volume = self.calculate_volume(self.current_price)
                tp_sl_rate = self.sl_tp_diff(data['atr'], data['adx'], adx_avg)

                pos = Position(
                    self, entry_price, entry_time, volume, self.leverage, order_type, tp_sl_rate
                )
            # if is downtrend
            # supertrend is downtrend
            # close < supertrend
            # close < vwap
            elif bool(data['supertrend_is_uptrend']) is False:\
                # data['supertrend_vwc'] < data['supertrend_trend'] \
                #and data['close'] < data['vwap']:
                logger.info('PriceAction::SHORT')
                # Position variables
                order_type = 'sell'
                entry_price = data['close']
                entry_time = data['time']
                volume = self.calculate_volume(self.current_price)
                tp_sl_rate = self.sl_tp_diff(data['atr'], data['adx'], adx_avg)

                pos = Position(
                    self, entry_price, entry_time, volume, self.leverage, order_type, tp_sl_rate
                )
        return pos