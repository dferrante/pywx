import logging
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level':'INFO',
            'class':'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['default'],
        'level': 'INFO',
        'propagate': True
    }
}


def setup_logger():
    logging.config.dictConfig(LOGGING_CONFIG)


def get_logger(name):
    setup_logger()
    return logging.getLogger(name)
