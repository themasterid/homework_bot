import logging
import os
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
    filename='my_logger.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(name)s, %(message)s'
)


def send_message(bot, message):
    bot.send_message(CHAT_ID, message)


def get_api_answer(url, current_timestamp):
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': current_timestamp}
    response = requests.get(url, headers=headers, params=payload)
    if response.status_code != 200:
        raise TheAnswerIsNot200Error('<ответ сервера не равен 200>')
    return response.json()


def parse_status(homework):
    """Статус изменился — анализируем его"""
    verdict = HOMEWORK_STATUSES.get(homework.get('status'))
    homework_name = homework.get('homework_name')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Изменился ли статус"""
    if response.get('homeworks') == []:
        raise EmptyDictionaryOrListError('<пустой словарь>')
    if response.get('homeworks')[0].get('status') not in HOMEWORK_STATUSES:
        raise UndocumentedStatusError('<недокументированный статус>')
    return parse_status(response.get('homeworks')[0])


def main():
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status_tmp = 'reviewing'
    response = get_api_answer(ENDPOINT, current_timestamp)
    while True:
        try:
            if response.get('homeworks') == []:
                current_timestamp = int(time.time())
                time.sleep(RETRY_TIME)
                continue
            response = get_api_answer(ENDPOINT, current_timestamp)
            status = response.get('homeworks')[0].get('status')
            if status != status_tmp:
                status_tmp = status
                message = check_response(response)
                send_message(bot, message)
                message = HOMEWORK_STATUSES.get(status_tmp)
                send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
            continue
        current_timestamp = int(time.time())


if __name__ == '__main__':
    main()
