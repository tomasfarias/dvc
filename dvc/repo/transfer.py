import logging

from dvc.path_info import PathInfo
from dvc.utils import resolve_output, resolve_paths

from . import locked

logger = logging.getLogger(__name__)


@locked
def transfer(
    self, url, target,
):
    from dvc.dvcfile import Dvcfile
    from dvc.stage import Stage, create_stage, restore_meta

    out = resolve_output(target, None)
    path, _, out = resolve_paths(self, out)

    stage = create_stage(Stage, target, path, deps=[url], outs=[out])
    restore_meta(stage)

    tree = stage.deps[0].tree
    from_info = stage.deps[0].path_info
    remote = self.cloud.get_remote(name=target)
    to_info = PathInfo(target + from_info.name)

    hash_md5 = remote.tree.transfer(from_info, to_info, tree)
    stage.outs[0].hash = hash_md5

    dvcfile = Dvcfile(self, stage.path)
    dvcfile.dump(stage)
