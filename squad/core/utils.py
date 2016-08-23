import random
import string


def random_key(length, chars=string.printable):
    return ''.join(random.SystemRandom().choice(chars) for _ in range(length))


def random_token(length):
    chars = string.ascii_letters + string.digits
    return random_key(length, chars=chars)
