import random


LOREM_IPSUM_WORDS = ['a', 'ac', 'accumsan', 'adipiscing', 'aenean', 'aliquam',
                     'amet', 'ante', 'arcu', 'at', 'augue', 'blandit',
                     'condimentum', 'congue', 'consectetur', 'consequat',
                     'convallis', 'cras', 'cursus', 'dapibus', 'diam',
                     'dictum', 'dignissim', 'dolor', 'donec', 'dui', 'duis',
                     'egestas', 'eget', 'eleifend', 'elementum', 'elit',
                     'enim', 'est', 'et', 'etiam', 'eu', 'euismod', 'ex',
                     'facilisis', 'faucibus', 'felis', 'feugiat', 'finibus',
                     'fringilla', 'fusce', 'gravida', 'id', 'in', 'integer',
                     'ipsum', 'justo', 'lacinia', 'laoreet', 'lectus',
                     'libero', 'ligula', 'lorem', 'luctus', 'maecenas',
                     'magna', 'mattis', 'mauris', 'maximus', 'metus', 'mi',
                     'molestie', 'mollis', 'nec', 'neque', 'nibh', 'nisi',
                     'nisl', 'non', 'nulla', 'nunc', 'odio', 'orci',
                     'ornare', 'pellentesque', 'phasellus', 'porttitor',
                     'praesent', 'pretium', 'pulvinar', 'purus', 'quis',
                     'risus', 'rutrum', 'sagittis', 'sapien', 'scelerisque',
                     'sed', 'sem', 'sit', 'sollicitudin', 'suscipit',
                     'tellus', 'tempus', 'tincidunt', 'tristique', 'turpis',
                     'ullamcorper', 'urna', 'ut', 'vel', 'velit', 'vestibulum',
                     'vitae', 'vivamus', 'viverra', 'vulputate']


def force_bytes(x, encoding='iso-8859-1'):
    if isinstance(x, bytes):
        return x
    else:
        return x.encode(encoding)


def lorem_ipsum():
    return ' '.join(            # sentences
        ' '.join(               # words
            random.sample(LOREM_IPSUM_WORDS, random.randint(5, 10))
        ).capitalize() + '.'
        for _ in range(random.randint(5, 10))
    )


def ellipsize(s, max_length=60):
    """
    >>> print(ellipsize(u'lorem ipsum dolor sit amet', 40))
    lorem ipsum dolor sit amet
    >>> print(ellipsize(u'lorem ipsum dolor sit amet', 20))
    lorem ipsum dolor...
    """
    if len(s) > max_length:
        ellipsis = '...'
        return s[:(max_length - len(ellipsis))] + ellipsis
    else:
        return s
