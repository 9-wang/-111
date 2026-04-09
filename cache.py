import time
from functools import wraps

class Cache:
    def __init__(self):
        self.cache = {}
        self.lock = {}  # 用于线程安全
        
    def get(self, key):
        """获取缓存值"""
        if key not in self.cache:
            return None
        
        # 检查缓存是否过期
        value, expiry = self.cache[key]
        if expiry is not None and time.time() > expiry:
            # 缓存已过期，删除它
            del self.cache[key]
            return None
        
        return value
    
    def set(self, key, value, expiry=None):
        """设置缓存值，可选过期时间（秒）"""
        if expiry is not None:
            expiry = time.time() + expiry
        self.cache[key] = (value, expiry)
    
    def delete(self, key):
        """删除缓存值"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        """清空所有缓存"""
        self.cache.clear()
    
    def cache_decorator(self, expiry=None):
        """装饰器，用于缓存函数结果"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                key = f"{func.__name__}:{args}:{kwargs}"
                
                # 检查缓存
                result = self.get(key)
                if result is not None:
                    return result
                
                # 执行函数
                result = func(*args, **kwargs)
                
                # 缓存结果
                self.set(key, result, expiry)
                
                return result
            return wrapper
        return decorator

# 创建全局缓存实例
cache = Cache()