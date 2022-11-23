import time
import threading
from loguru import logger
from sqlalchemy import true
from utils.constants import Constants
from utils.trade_logger import filelog

class Position:
    TP = 'tp'
    SL = 'sl'

    def __init__(self, parent, entry_price, entry_time, volume, leverage, order_type, tp_sl_rate, tp_sl_trigger_rate):
        self.parent = parent

        self.volume = volume
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.amount = 0
        self.mark_price = 0
        self.liq_price = 0
        self.leverage = leverage
        self.unrealised_profit = 0
        self.isolated_margin = 0
        self.isolated_wallet = 0
        self.notional = 0
        self.max_notional = 0
        self.margin_type = None

        self.tp = 0
        self.sl = 0
        self.tp_trigger = 0
        self.sl_trigger = 0

        self.trigger_exit_price = None
        self.exit_price = 0
        self.exit_time = None
        self.profit = 0
        self.is_closed = False

        self.orderId = None
        self.clientOrderId = None
        self.orderFilled = False

        self.tpOrderId = None
        self.tpClientOrderId = None
        self.slOrderId = None
        self.slClientOrderId = None

        
        self.tp_sl_rate = tp_sl_rate
        self.tp_sl_trigger_rate = tp_sl_trigger_rate
        self.order_type = order_type
        self.update_tp_sl()
        self.thread = None

    def update_tp_sl(self):
        if self.order_type == 'buy':
            self.tp = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
            # sl and tp order trigger tp and sl
            self.tp_trigger = self.parent.get_precise_price(self.entry_price + self.tp_sl_trigger_rate)
            self.sl_trigger = self.parent.get_precise_price(self.entry_price - self.tp_sl_trigger_rate)
        else:
            self.tp = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)
            # sl and tp order trigger tp and sl
            self.tp_trigger = self.parent.get_precise_price(self.entry_price - self.tp_sl_trigger_rate)
            self.sl_trigger = self.parent.get_precise_price(self.entry_price + self.tp_sl_trigger_rate)


    def update_profit(self):
        self.profit = (self.exit_price - self.entry_price) * self.volume if self.order_type == 'buy' \
                                                    else (self.entry_price - self.exit_price) * self.volume

    def change_price(self, price, percentage):
        return self.parent.get_precise_price(price + (price * percentage) / 100)

    def try_close(self):
        closed = False
        while closed is False:
            if self.is_closed:
                closed = True
            else:
                try:
                    price = self.parent.get_current_price()
                    # If the current price is leading the take profit mark, use the tp/sl trigger rate
                    # with the current price to create another tp that leads the current price
                    if self.order_type == 'buy' and price >= self.tp:
                        self.tp = self.parent.get_precise_price(price + self.tp_sl_trigger_rate / 1.5)
                        self.sl = self.parent.get_precise_price(price - self.tp_sl_trigger_rate / 1.5)
                    elif self.order_type == 'sell' and price <= self.tp:
                        self.tp = self.parent.get_precise_price(price - self.tp_sl_trigger_rate / 1.5)
                        self.sl = self.parent.get_precise_price(price + self.tp_sl_trigger_rate / 1.5)
                    elif self.order_type == 'buy' and price <= self.sl:
                        self.sl = self.parent.get_precise_price(price - self.tp_sl_trigger_rate / 1.5)
                        self.tp = self.parent.get_precise_price(price + self.tp_sl_trigger_rate / 1.5)
                    elif self.order_type == 'sell' and price >= self.sl:
                        self.sl = self.parent.get_precise_price(price + self.tp_sl_trigger_rate / 1.5)
                        self.tp = self.parent.get_precise_price(price - self.tp_sl_trigger_rate / 1.5)
                    self.parent.take_profit(self)
                    self.parent.stop_loss(self)
                    closed = True
                except Exception as e:
                    log = f"==NotClosed:TP.error==\n{str(e)}"
                    filelog(
                        f'{Constants.log_dir_name}/{Constants.pos_log_filename}', log + Constants.log_text_nl
                    )
                    # APIError(code=-4129): Time in Force (TIF) GTE can only be used with open positions or open orders. 
                    # Please ensure that open orders or positions are available.
                    if 'apierror(code=-4129)' in str(e).lower():
                        self.is_closed = True
                    else:
                        closed = False
                if not closed:
                    log = f"==NotClosed==\n{str(self.asdict())}"
                    filelog(
                        f'{Constants.log_dir_name}/{Constants.pos_log_filename}', log + Constants.log_text_nl
                    )
                    time.sleep(2)
        self.thread.join()
        self.thread = None
        log = f"==!Closed!==\n{str(self.asdict())}"
        filelog(
            f'{Constants.log_dir_name}/{Constants.pos_log_filename}', log + Constants.log_text_nl
        )
                

    def close_position(self, action=None, trigger_exit_price=None):
        if trigger_exit_price is not None:
            self.action = action
            self.trigger_exit_price = trigger_exit_price

        if self.thread is None:
            self.thread = threading.Thread(target = self.try_close)
            self.thread.start()

    def asdict(self):
        return {
            'volume': self.volume,	
            'entry_price': self.entry_price,	
            'entry_time': self.entry_time,	
            'amount': self.amount,	
            'mark_price': self.mark_price,	
            'liq_price': self.liq_price,	
            'leverage': self.leverage,	
            'unrealised_profit': self.unrealised_profit,	
            'isolated_margin': self.isolated_margin,	
            'isolated_wallet': self.isolated_wallet,	
            'notional': self.notional,	
            'max_notional': self.max_notional,	
            'margin_type': self.margin_type,	

            'tp': self.tp,	
            'sl': self.sl,
            'tp_trigger': self.tp_trigger,	
            'sl_trigger': self.sl_trigger,	

            'trigger_exit_price': self.trigger_exit_price,	
            'exit_price': self.exit_price,	
            'exit_time': self.exit_time,	
            'profit': self.profit,	
            'is_closed': self.is_closed,	

            'orderId': self.orderId,	
            'clientOrderId': self.clientOrderId,	
            'orderFilled': self.orderFilled,	

            'tpOrderId': self.tpOrderId,	
            'tpClientOrderId': self.tpClientOrderId,	
            'slOrderId': self.slOrderId,	
            'slClientOrderId': self.slClientOrderId,	

            
            'tp_sl_rate': self.tp_sl_rate,	
            'tp_sl_trigger_rate': self.tp_sl_trigger_rate,
            'order_type': self.order_type,	
        }