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

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""

    pass


class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""

    pass


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""

    pass


logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'my_logger.log',
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


def send_message(bot, message):
    """Отправка сообщения в Телеграмм."""
    try:
        bot.send_message(CHAT_ID, message)
        logging.info(f'Отправка сообщения в Telegram выполнена: {message}')
    except Exception as err:
        logging.error(f'Отправка сообщения в Telegram не выполнена: {err}')


def get_api_answer(url, current_timestamp):
    """Получение данных с API YP."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': current_timestamp}
    response = requests.get(url, headers=headers, params=payload)
    if response.status_code != 200:
        logging.error(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}')
        raise TheAnswerIsNot200Error(f'Код ответа API: {response.status_code}')
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
        exit()
    if TELEGRAM_TOKEN is None:
        logging.critical(
            'Отсутствует обязательная переменная окружения:'
            ' "TELEGRAM_TOKEN" Программа принудительно остановлена.')
        exit()
    if CHAT_ID is None:
        logging.critical(
            'Отсутствует обязательная переменная окружения:'
            ' "CHAT_ID" Программа принудительно остановлена.')
        exit()


def main():
    """Главная функция запуска бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    count_errors = 0
    status_tmp = 'reviewing'
    while True:
        try:
            response = get_api_answer(ENDPOINT, int(time.time()))
            if response.get('homeworks') == []:
                time.sleep(RETRY_TIME)
                continue
            status = response.get('homeworks')[0].get('status')
            if status != status_tmp:
                status_tmp = status
                message = check_response(response)
                send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if count_errors < 1:
                count_errors += 1
                logging.StreamHandler(sys.stdout)
                logging.critical(message)
                send_message(bot, message)
                continue
            logging.StreamHandler(sys.stdout)
            logging.critical(message)
            time.sleep(RETRY_TIME)
            continue


if __name__ == '__main__':
    main()
