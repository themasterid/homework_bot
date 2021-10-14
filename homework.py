import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from telegram import TelegramError

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 60 * 10
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
    '%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
handler.setFormatter(formatter)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""


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
            f'Сообщение в Telegram отправлено: {message}')
    except TelegramError as telegram_error:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(url, current_timestamp):
    """Получение данных с API YP."""
    try:
        headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
        payload = {'from_date': current_timestamp}
        response = requests.get(url, headers=headers, params=payload)
    except requests.exceptions.RequestException as request_error:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Код ответа API: RequestException - {request_error}')
        raise RequestExceptionError(
            f'Код ответа API: RequestException - {request_error}')
    except ValueError as value_error:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Код ответа API: ValueError - {value_error}')
        raise RequestExceptionError(
            f'Код ответа API: ValueError - {value_error}')
    if response.status_code != 200:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Эндпоинт {ENDPOINT} недоступен.'
            f'Код ответа API (status_code != 200): {response.status_code}')
        raise TheAnswerIsNot200Error(
            f'Эндпоинт {ENDPOINT} недоступен.'
            f'Код ответа API (status_code != 200): {response.status_code}')
    return response.json()


def parse_status(homework):
    """Анализируем статус если изменился."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')
    if status == []:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Ошибка пустое значение status: {status}')
        raise EmptyDictionaryOrListError(
            f'Ошибка пустое значение status: {status}')
    if homework_name == []:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Ошибка пустое значение homework_name: {homework_name}')
        raise EmptyDictionaryOrListError(
            f'Ошибка пустое значение homework_name: {homework_name}')
    if status not in HOMEWORK_STATUSES:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Ошибка недокументированный статус: {status}')
        raise UndocumentedStatusError(
            f'Ошибка недокументированный статус: {status}')
    verdict = HOMEWORK_STATUSES.get(homework.get('status'))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверяем данные в response."""
    homeworks = response.get('homeworks')[0]
    if homeworks == []:
        logging.StreamHandler(sys.stdout)
        logging.error(
            f'Пустое значение в homeworks: {homeworks}')
        raise EmptyDictionaryOrListError(
            f'Пустое значение в homeworks: {homeworks}')
    return parse_status(homeworks)


def check_tokens():
    """Проверка наличия токенов."""
    if PRACTICUM_TOKEN is None:
        logging.StreamHandler(sys.stdout)
        logging.critical(
            'Отсутствует обязательная переменная окружения: '
            'PRACTICUM_TOKEN. Программа принудительно остановлена.')
        return False
    if TELEGRAM_TOKEN is None:
        logging.StreamHandler(sys.stdout)
        logging.critical(
            'Отсутствует обязательная переменная окружения: '
            'TELEGRAM_TOKEN. Программа принудительно остановлена.')
        return False
    if CHAT_ID is None:
        logging.StreamHandler(sys.stdout)
        logging.critical(
            'Отсутствует обязательная переменная окружения: '
            'CHAT_ID. Программа принудительно остановлена.')
        return False
    return True


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    errors = True
    status_tmp = 'reviewing'
    while True:
        try:
            response = get_api_answer(
                ENDPOINT, current_timestamp - RETRY_TIME)
            if response.get('homeworks') == []:
                current_timestamp = int(time.time())
                time.sleep(RETRY_TIME)
                continue
            status = response.get('homeworks')[0].get('status')
            if status != status_tmp:
                status_tmp = status
                message = check_response(response)
                send_message(bot, message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logging.StreamHandler(sys.stdout)
            logging.critical(message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
            continue


if __name__ == '__main__':
    main()
