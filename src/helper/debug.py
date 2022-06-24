from functools import wraps
from time import time
from typing import Callable

from .logger import logger

func_debug_cnt = 0


def function_debuger(print_input=False, print_output=False, limit_input=200):
    def decorator_debuger(func):
        def wrapper(*args, **kwargs):
            global func_debug_cnt
            now = time()
            if len(args) > 0 and isinstance(args[0], object):
                debug_info = f"{args[0].__class__.__name__} {func.__name__}"
            else:
                debug_info = func.__name__
            logger.debug("  " * func_debug_cnt + f">> {debug_info}")
            func_debug_cnt += 1
            try:
                if print_input:
                    logger.debug(
                        "  " * func_debug_cnt + f"-> {args} {kwargs}"[:limit_input]
                    )
                result = func(*args, **kwargs)
                if print_output:
                    logger.debug("  " * func_debug_cnt + f"<- {result}")
            except Exception as e:
                raise e
            finally:
                func_debug_cnt -= 1
            logger.debug(
                "  " * func_debug_cnt + f"<< {debug_info} %.2fs" % (time() - now)
            )
            return result

        return wrapper

    if isinstance(print_input, Callable):
        logger.debug("print_input -------_> %r", print_input)
        func = print_input
        print_input = False
        return decorator_debuger(func)
    return decorator_debuger


def function_debuger_with_resule(func):
    return function_debuger(print_output=True)(func)
