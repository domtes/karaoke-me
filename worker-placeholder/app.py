import logging
import threading


logger = logging.getLogger('worker')


def fake_it():
    threading.Timer(5.0, fake_it).start()
    logger.info('Checking for work')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    fake_it()
