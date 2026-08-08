import asyncio
from collections.abc import Sequence

import colorama

import Utils
from CommonClient import get_base_parser, handle_url_arg


def launch_marble_balance_client(*args: Sequence[str]) -> None:
    from .client import main

    parser = get_base_parser(description="Marbles! Balance Challenge Archipelago Client")
    parser.add_argument("--name", default=None, help="Slot Name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url or .apmbc output file")
    parsed_args = parser.parse_args(args)

    if parsed_args.url and str(parsed_args.url).endswith(".apmbc"):
        parsed_args.patch_file = parsed_args.url
        parsed_args.url = None
    else:
        parsed_args.patch_file = None
        parsed_args = handle_url_arg(parsed_args, parser=parser)

    colorama.just_fix_windows_console()
    Utils.init_logging("MarbleBalanceClient", exception_logger="Client")
    asyncio.run(main(parsed_args))
    colorama.deinit()
