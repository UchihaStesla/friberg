import time
import random

def custom_uuid_implementation():
    """模拟cn()函数的自定义实现"""
    template = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
    
    # 获取当前时间戳(毫秒)
    timestamp = int(time.time() * 1000)
    
    # 为了模拟performance.now()，使用更精确的时间
    perf_now = time.perf_counter() * 1000
    
    def replace_char(c):
        nonlocal timestamp, perf_now
        
        # 使用时间戳或性能计数器加上随机数
        rand = random.random() * 16
        
        if timestamp > 0:
            s = int((timestamp + rand) % 16)
            timestamp = timestamp // 16
        else:
            s = int((perf_now + rand) % 16)
            perf_now = perf_now // 16
            
        # 处理'x'和'y'字符的替换
        if c == 'x':
            return format(s, 'x')
        else:  # 处理'y'
            return format(s & 3 | 8, 'x')
    
    # 使用替换函数替换模板中的每个x和y
    result = ''
    for char in template:
        if char in ['x', 'y']:
            result += replace_char(char)
        else:
            result += char        
    return result

