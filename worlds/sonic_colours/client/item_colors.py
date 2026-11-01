STANDARD = {'progression': '#AF70FF', 'useful': '#305BD8', 'filler': '#64C8FF', 'trap': '#F05252'}
COLORBLIND = {'progression': '#F0E442', 'useful': '#0072B2', 'filler': '#999999', 'trap': '#D55E00'}


def category(flags):
    return 'trap' if flags & 4 else 'progression' if flags & 1 else 'useful' if flags & 2 else 'filler'


def item_color(flags, colorblind=False):
    return (COLORBLIND if colorblind else STANDARD)[category(flags)]
