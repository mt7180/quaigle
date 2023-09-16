def register_page(page_dict: dict[str, callable])-> callable:
    """register page automatically in page dict"""
    def inner(func): 
        page_dict[func.__name__] = func
    return inner