import json
import logging
import os
import time
from datetime import datetime

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

CODE_API_MSG = 'Код ответа API: '
EMPTY_VAL_MSG = 'Ошибка пустое значение: '
NOT_DOC_ST_MSG = 'Ошибка недокументированный статус: '
NO_TOKENS_MSG = 'Отсутствует обязательная переменная окружения: '
STOP_PROG_MSG = 'Программа принудительно остановлена.'

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
stdout_ = logging.StreamHandler()
logger = logging.getLogger(__name__)
logger.addHandler(stdout_)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(CHAT_ID, message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(url, current_timestamp):
    """Получение данных с API YP."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': current_timestamp}
    answer = {'homeworks': [], 'current_date': current_timestamp}
    try:
        response = requests.get(url, headers=headers, params=payload)
    except requests.exceptions.RequestException as request_error:
        logger.error(
            f'{CODE_API_MSG}{request_error}')
        raise RequestExceptionError(
            f'{CODE_API_MSG}{request_error}')
        return answer
    except ValueError as value_error:
        logger.error(
            f'{CODE_API_MSG}{value_error}')
        raise ValueError(
            f'{CODE_API_MSG}{value_error}')
        return answer
    if response.status_code != 200:
        logger.error(
            f'Эндпоинт {url} недоступен. '
            f'{CODE_API_MSG}{response.status_code}')
        raise TheAnswerIsNot200Error(
            f'Эндпоинт {url} недоступен. '
            f'{CODE_API_MSG}{response.status_code}')
        return answer
    try:
        return response.json()
    except json.JSONDecodeError as error:
        logger.error(f'JSONDecodeError: {error}')
        return answer


def parse_status(homework):
    """Анализируем статус если изменился."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')
    if status is None:
        logger.error(
            f'{EMPTY_VAL_MSG}{status}')
        raise EmptyDictionaryOrListError(
            f'{EMPTY_VAL_MSG}{status}')
    if homework_name is None:
        logger.error(
            f'{EMPTY_VAL_MSG}{homework_name}')
        raise EmptyDictionaryOrListError(
            f'{EMPTY_VAL_MSG}{homework_name}')
    if status not in HOMEWORK_STATUSES:
        logger.error(
            f'{NOT_DOC_ST_MSG}{status}')
        raise UndocumentedStatusError(
            f'{NOT_DOC_ST_MSG}{status}')
    verdict = HOMEWORK_STATUSES[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверяем данные в response."""
    if response['homeworks'] == []:
        logger.error(
            f'{EMPTY_VAL_MSG}{response["homeworks"]}')
        raise EmptyDictionaryOrListError(
            f'{EMPTY_VAL_MSG}{response["homeworks"]}')
    homeworks = response.get('homeworks')[0]
    if homeworks is None:
        logger.error(
            f'{EMPTY_VAL_MSG}{homeworks}')
        raise EmptyDictionaryOrListError(
            f'{EMPTY_VAL_MSG}{homeworks}')
    status = response.get('homeworks')[0].get('status')
    if status not in HOMEWORK_STATUSES:
        logger.error(
            f'{NOT_DOC_ST_MSG}{status}')
        raise UndocumentedStatusError(
            f'{NOT_DOC_ST_MSG}{status}')
    return homeworks


def check_tokens():
    """Проверка наличия токенов."""
    if PRACTICUM_TOKEN is None:
        logger.critical(
            f'{NO_TOKENS_MSG}PRACTICUM_TOKEN. {STOP_PROG_MSG}')
        return
    if TELEGRAM_TOKEN is None:
        logger.critical(
            f'{NO_TOKENS_MSG}TELEGRAM_TOKEN. {STOP_PROG_MSG}')
        return
    if CHAT_ID is None:
        logger.critical(
            f'{NO_TOKENS_MSG}CHAT_ID. {STOP_PROG_MSG}')
        return
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
            response = get_api_answer(ENDPOINT, current_timestamp)
            if response['homeworks'] == []:
                logger.info(
                    f"{datetime.now().strftime('%H:%M:%S')}:"
                    "Изменений нет, ждем 10 минут и проверяем API")
                time.sleep(RETRY_TIME)
                current_timestamp = int(time.time() - RETRY_TIME)
                continue
            status = check_response(response).get('status')
            if status != status_tmp:
                status_tmp = status
                message = parse_status(response['homeworks'][0])
                send_message(bot, message)
            time.sleep(RETRY_TIME)
            current_timestamp = response['current_date'] - RETRY_TIME
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logger.critical(message)
            time.sleep(RETRY_TIME)
            continue


if __name__ == '__main__':
    main()
