"""Backward-compatible entry point — prefer wsgi.py."""
from wsgi import app

if __name__ == '__main__':
    import runpy
    runpy.run_module('wsgi', run_name='__main__')
