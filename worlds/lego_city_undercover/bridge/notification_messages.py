"""Build receipt and server-confirmed send messages from structured AP data."""


def receipt_message(item_name, sender, own_slot, player_names):
    if sender == own_slot:
        return f'You found your own {item_name}!'
    return f'You received {item_name} from {player_names.get(sender, f"Player {sender}")}!'


def item_classification(flags):
    if flags & 1:return 'progression'
    if flags & 2:return 'useful'
    if flags & 4:return 'trap'
    return 'filler'


def sent_message(packet, own_slot, item_names, player_names):
    if packet.get('type') != 'ItemSend':return None
    item=packet.get('item');recipient=packet.get('receiving')
    if item is None or item.player != own_slot or recipient == own_slot or recipient is None:
        return None
    name=item_names.lookup_in_slot(item.item,recipient)
    return dict(key=f'sent:{item.player}:{item.location}:{recipient}:{item.item}',
        text=f'You sent {name} to {player_names.get(recipient, f"Player {recipient}")}!',
        classification=item_classification(item.flags))
