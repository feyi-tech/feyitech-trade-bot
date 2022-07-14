import time
import threading
from loguru import logger
from sqlalchemy import true
from utils.constants import Constants
from utils.trade_logger import filelog

class Position:
    TP = 'tp'
    SL = 'sl'

    def __init__(self, parent, entry_price, entry_time, volume, leverage, order_type, tp_sl_rate, tp_sl_rate_trigger):
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
        self.tp_sl_rate_trigger = tp_sl_rate_trigger
        self.order_type = order_type
        self.update_tp_sl()
        self.thread = None

    def update_tp_sl(self):
        if self.order_type == 'buy':
            self.tp = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
            # sl and tp order trigger tp and sl
            self.tp_trigger = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate_trigger)
            self.sl_trigger = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate_trigger)
        else:
            self.tp = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)
            # sl and tp order trigger tp and sl
            self.tp_trigger = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate_trigger)
            self.sl_trigger = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate_trigger)


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
                tp_closed = self.tpOrderId is not None
                sl_closed = self.slOrderId is not None
                if not tp_closed:
                    try:
                        self.parent.take_profit(self)
                        tp_closed = True
                    except:
                        tp_closed = False
                if not sl_closed:
                    try:
                        self.parent.stop_loss(self)
                        sl_closed = True
                    except:
                        sl_closed = False
                        
                closed = tp_closed and sl_closed
                if not closed:
                    time.sleep(2)
        self.thread.join()
        self.thread = None
                

    def close_position(self, action=None, trigger_exit_price=None):
        if trigger_exit_price is not None:
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
            'tp_sl_rate_trigger': self.tp_sl_rate_trigger,
            'order_type': self.order_type,	
        }