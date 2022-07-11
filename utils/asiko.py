
import datetime as DT

def time_diff(t2, t1):
    if type(t1) == type(0) or type(t1) == type(0.1) or type(t2) == type(0) or type(t2) == type(0.1):
        return None
    return t2 - t1

def time_diff_now(t):
    if type(t) == type(0) or type(t) == type(0.1):
        return None
    t2 = DT.datetime.now()
    # t1 = DT.datetime.fromisoformat(t) # string to datetime
    return t2 - t