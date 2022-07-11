import math

def roundup(x, nearest):
    return int(math.ceil(x / float(nearest))) * int(nearest)

def op_values_at_index(list_of_list, index, op, limit=None):
    result = 0
    arrs = list_of_list
    if limit is not None:
        arrs = arrs[0:limit]
    for arr in arrs:
        result = op(result, arr[index])
    return result
        
def add(a, b):
    return float(a) + float(b)