"""Change-only action context history; deliberately independent of check events."""


class ContextTracker:
    def __init__(self):
        self.previous = None

    def update(self, context):
        if context.get('status') != 'read':
            return None
        current = (context['index'], context['name'])
        if current == self.previous:
            return None
        event = dict(kind='context_change', index=current[0], name=current[1],
                     previous=dict(index=self.previous[0], name=self.previous[1]) if self.previous else None,
                     initial=self.previous is None)
        self.previous = current
        return event
