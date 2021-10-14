import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 1
TIME_MINUS_MONTH = 2592000
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'program.log',
    maxBytes=50000000,
    backupCount=5)
logger.addHandler(handler)
stdout_ = logging.StreamHandler(sys.stdout)
rootlogger = logging.getLogger()
rootlogger.addHandler(stdout_)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""

    pass


class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""

    pass


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


class TimeoutExceptionError(Exception):
    """Ошибка таймаута."""


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        # bot.send_message(CHAT_ID, message)
        logging.StreamHandler(sys.stdout)
        logging.info(
            f'\nСообщение в Telegram отправлено:\n{message}')
    except Exception as err:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'\nСообщение в Telegram не отправлено:\n{err}')


def get_api_answer(url, current_timestamp):
    """Получение данных с API YP."""
    try:
        headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
        payload = {'from_date': current_timestamp}
        response = requests.get(url, headers=headers, params=payload)
    except requests.exceptions.Timeout as timeout_error:
        logging.StreamHandler(sys.stdout)
        raise TimeoutExceptionError(
            f'\nКод ответа API: Timeout - {timeout_error}')
    except requests.exceptions.RequestException as request_error:
        logging.StreamHandler(sys.stdout)
        raise RequestExceptionError(
            f'\nКод ответа API: RequestException - {request_error}')
    except ValueError as value_error:
        logging.StreamHandler(sys.stdout)
        raise RequestExceptionError(
            f'\nКод ответа API: ValueError - {value_error}')

    if response.status_code != 200:
        logging.StreamHandler(sys.stdout)
        raise TheAnswerIsNot200Error(
            f'\nЭндпоинт {ENDPOINT} недоступен.'
            f'\nКод ответа API (status_code != 200): {response.status_code}')
    return response.json()


def parse_status(homework):
    """Статус изменился — анализируем его."""
    verdict = HOMEWORK_STATUSES.get(homework.get('status'))
    homework_name = homework.get('homework_name')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверяем изменился ли статус."""
    homeworks = response.get('homeworks')[0]
    status = homeworks.get('status')
    if status == []:
        logging.error(
            f'Ошибка пустое значение: {homeworks}')
        raise EmptyDictionaryOrListError(
            f'Ошибка пустое значение: {homeworks}')
    if status not in HOMEWORK_STATUSES:
        logging.error(
            f'Ошибка недокументированный статус: {status}')
        raise UndocumentedStatusError(
            f'Ошибка недокументированный статус: {status}')
    return parse_status(homeworks)


def check_tokens():
    """Проверка наличия токенов."""
    if PRACTICUM_TOKEN is None:
        logging.critical(
            'Отсутствует обязательная переменная окружения:'
            ' "PRACTICUM_TOKEN" Программа принудительно остановлена.')
        return False
    if TELEGRAM_TOKEN is None:
        logging.critical(
            'Отсутствует обязательная переменная окружения:'
            ' "TELEGRAM_TOKEN" Программа принудительно остановлена.')
        return False
    if CHAT_ID is None:
        logging.critical(
            'Отсутствует обязательная переменная окружения:'
            ' "CHAT_ID" Программа принудительно остановлена.')
        return False
    return True


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - TIME_MINUS_MONTH
    errors = True
    status_tmp = 'reviewing'
    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            status = response.get('homeworks')[0].get('status')
            if status != status_tmp:
                status_tmp = status
                message = check_response(response)
                send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logging.StreamHandler(sys.stdout)
            logging.critical(message)
            current_timestamp = int(time.time()) - TIME_MINUS_MONTH
            time.sleep(RETRY_TIME)
            continue
        current_timestamp = int(time.time()) - TIME_MINUS_MONTH


if __name__ == '__main__':
    main()
