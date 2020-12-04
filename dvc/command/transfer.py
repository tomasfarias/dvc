import argparse
import logging

from dvc.command.base import CmdBase, append_doc_link
from dvc.exceptions import DvcException

logger = logging.getLogger(__name__)


class CmdTransfer(CmdBase):
    def run(self):
        try:
            self.repo.transfer(
                self.args.url, self.args.remote,
            )

        except DvcException:
            logger.exception(
                "failed to transfer '{}' to '{}'".format(
                    self.args.url, self.args.remote
                )
            )
            return 1
        return 0


def add_parser(subparsers, parent_parser):
    TRANSFER_HELP = "Transfer a file to remote, and track it."

    parser = subparsers.add_parser(
        "transfer",
        parents=[parent_parser],
        description=append_doc_link(TRANSFER_HELP, "transfer"),
        help=TRANSFER_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url", help="Location of file to transfer.",
    )
    parser.add_argument(
        "remote", help="",
    )
    parser.set_defaults(func=CmdTransfer)
