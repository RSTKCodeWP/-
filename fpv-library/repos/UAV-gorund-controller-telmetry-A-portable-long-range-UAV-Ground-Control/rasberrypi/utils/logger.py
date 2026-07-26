import logging

logging.basicConfig(

    filename="uav_ground_station.log",

    level=logging.INFO,

    format=(
        '%(asctime)s '
        '%(levelname)s '
        '%(message)s'
    )
)

logger = logging.getLogger()


def log_info(message):

    logger.info(message)


def log_error(message):

    logger.error(message)