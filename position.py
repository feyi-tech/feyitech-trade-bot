from loguru import logger
from sqlalchemy import true
from utils.constants import Constants
from utils.trade_logger import filelog

class Position:
    TP = 'tp'
    SL = 'sl'

    def __init__(self, parent, entry_price, entry_time, volume, leverage, order_type, tp_sl_rate):
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
        # used to decrease the close condition price to the latest price so the trade can close 
        # as quick as possible
        self.tp_temp = 0
        self.sl_temp = 0

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
        self.order_type = order_type
        self.update_tp_sl()

    def update_tp_sl(self):
        if self.order_type == 'buy':
            self.tp = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
        else:
            self.tp = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)


    def update_profit(self):
        self.profit = (self.exit_price - self.entry_price) * self.volume if self.order_type == 'buy' \
                                                    else (self.entry_price - self.exit_price) * self.volume

    def change_price(self, price, percentage):
        return self.parent.get_precise_price(price + (price * percentage) / 100)

    def close_position(self, action=None, trigger_exit_price=None):
        if trigger_exit_price is not None:
            self.trigger_exit_price = trigger_exit_price

        current_price = trigger_exit_price if trigger_exit_price is not None else self.parent.get_current_price()

        closed = False
        close_price_change_percentage = 0.1
        close_price_change_percentage_diff = 0.1
        min_close_price_change_percentage = 0.1
        max_close_price_change_percentage = 0.2
        while closed is False:
            closed = self.try_close(current_price, close_price_change_percentage)
            close_price_change_percentage = close_price_change_percentage + close_price_change_percentage_diff
            if close_price_change_percentage > max_close_price_change_percentage:
                close_price_change_percentage = min_close_price_change_percentage

    def try_close(self, current_price, percentage):
        price_up = self.change_price(current_price, percentage)
        price_down = self.change_price(current_price, percentage * -1)

        action_validation = None
        if (current_price <= float(self.sl) and self.order_type == 'buy'):
            try:
                self.parent.stop_loss(self)
                self.parent.take_profit(self)
                return True
            except:
                self.sl = price_down
                self.tp_temp = price_up
                action_validation = Position.SL
                try:
                    self.parent.stop_loss(self)
                    self.parent.take_profit(self)
                    return True
                except:
                    return False
        elif (current_price >= float(self.sl) and self.order_type == 'sell'):
            try:
                self.parent.stop_loss(self)
                self.parent.take_profit(self)
                return True
            except:
                self.sl = price_up
                self.tp_temp = price_down
                action_validation = Position.SL
                try:
                    self.parent.stop_loss(self)
                    self.parent.take_profit(self)
                    return True
                except:
                    return False
        elif (current_price >= float(self.tp) and self.order_type == 'buy'):
            try:
                self.parent.take_profit(self)
                self.parent.stop_loss(self)
                return True
            except:
                self.tp = price_up
                self.sl_temp = price_down
                action_validation = Position.TP
                try:
                    self.parent.take_profit(self)
                    self.parent.stop_loss(self)
                    return True
                except:
                    return False
        elif (current_price <= float(self.tp) and self.order_type == 'sell'):
            try:
                self.parent.take_profit(self)
                self.parent.stop_loss(self)
                return True
            except:
                self.tp = price_down
                self.sl_temp = price_up
                action_validation = Position.TP
                try:
                    self.parent.take_profit(self)
                    self.parent.stop_loss(self)
                    return True
                except:
                    return False
        else:
            try:
                self.parent.take_profit(self)
                self.parent.stop_loss(self)
                return True
            except:
                self.tp_temp = price_up if self.order_type == 'buy' else price_down
                self.sl_temp = price_up if self.order_type == 'sell' else price_down
                try:
                    self.parent.take_profit(self)
                    self.parent.stop_loss(self)
                    return True
                except:
                    return False


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
            'tp_temp': self.tp_temp,	
            'sl_temp': self.sl_temp,	

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
            'order_type': self.order_type,	
        }