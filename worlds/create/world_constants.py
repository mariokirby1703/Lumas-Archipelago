GAME_NAME = "Create"

ITEM_ID_BASE = 0x43520000
LOCATION_ID_BASE = 0x43530000

WORLD_KEYS = (
    "W01",
    "W02",
    "W03",
    "W04",
    "W05",
    "W06",
    "W07",
    "W08",
    "W09",
    "W10",
    "W11",
    "W12",
    "W13",
    "W14",
)

WORLD_NAMES = {
    "W01": "Theme Park",
    "W02": "Transportopia",
    "W03": "Family Home",
    "W04": "Outer Space",
    "W05": "The Great Outdoors",
    "W06": "Ancient History",
    "W07": "Future World",
    "W08": "Urban Sports",
    "W09": "Pirate",
    "W10": "Darkworld",
    "W11": "Theme Park II",
    "W12": "Family Home II",
    "W13": "Outer Space II",
    "W14": "Future World II",
}

WORLD_KEY_BY_NAME = {name: key for key, name in WORLD_NAMES.items()}

HUB_WORLD_KEY = "HUB"

FIRST_TEN_WORLDS = WORLD_KEYS[:10]
II_WORLDS = WORLD_KEYS[10:]

CHALLENGES_PER_WORLD = 10
CREATE_CHAINS_PER_WORLD = 5

ITEM_VICTORY = "Victory"
ITEM_SPARK_1 = "1 Spark"
ITEM_SPARK_2 = "2 Sparks"
ITEM_SPARK_3 = "3 Sparks"
ITEM_SPARK_6 = "6 Sparks"
SPARK_ITEM_AMOUNTS = {
    ITEM_SPARK_1: 1,
    ITEM_SPARK_2: 2,
    ITEM_SPARK_3: 3,
    ITEM_SPARK_6: 6,
}
SPARK_ITEM_BY_AMOUNT = {amount: item for item, amount in SPARK_ITEM_AMOUNTS.items()}
FILLER_ITEMS = ("Creativity",)

# PAL Create. GameTDB lists the PAL Wii disc as SECP69.
GAME_ID_ADDRESS = 0x80000000
SUPPORTED_GAME_IDS = (b"SECP69",)
SUPPORTED_GAME_ID_LABEL = "SECP69"
