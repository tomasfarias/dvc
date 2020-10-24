import logging
import os
import threading
from collections import deque
from contextlib import contextmanager
from urllib.parse import urlparse

from funcy import cached_property, wrap_prop

from dvc.path_info import CloudURLInfo
from dvc.progress import Tqdm
from dvc.scheme import Schemes

from .base import BaseTree

logger = logging.getLogger(__name__)


def update_pbar(pbar):
    """Update pbar to accept the two arguments passed by hdfs"""

    def update(_, bytes_transfered):  # No use for first argument (path)
        if bytes_transfered == -1:
            return
        pbar.update(bytes_transfered)

    return update


class WebHDFSTree(BaseTree):
    scheme = Schemes.WEBHDFS
    PATH_CLS = CloudURLInfo
    REQUIRES = {"hdfs": "hdfs"}
    REGEX = r"^webhdfs://((?P<user>.*)@)?.*$"

    def __init__(self, repo, config):
        super().__init__(repo, config)

        self.path_info = None
        url = config.get("url")
        if not url:
            return

        parsed = urlparse(url)
        user = parsed.username or config.get("user")

        self.path_info = self.PATH_CLS.from_parts(
            scheme="webhdfs",
            host=parsed.hostname,
            user=user,
            port=parsed.port,
            path=parsed.path,
        )

        self.hdfscli_config = config.get("hdfscli_config")
        self.token = config.get("webhdfs_token")
        self.alias = config.get("webhdfs_alias")

    @wrap_prop(threading.Lock())
    @cached_property
    def hdfs_client(self):
        import hdfs

        logger.debug("URL: %s", self.path_info)
        logger.debug("HDFSConfig: %s", self.hdfscli_config)

        try:
            client = hdfs.config.Config(  # pylint: disable=no-member
                self.hdfscli_config
            ).get_client(self.alias)
        except hdfs.util.HdfsError:  # pylint: disable=no-member
            http_url = f"http://{self.path_info.host}:{self.path_info.port}"

            if self.token is not None:
                client = hdfs.TokenClient(  # pylint: disable=no-member
                    http_url, self.token
                )
            else:
                client = hdfs.InsecureClient(  # pylint: disable=no-member
                    http_url, self.path_info.user
                )

        return client

    @contextmanager
    def open(self, path_info, mode="r", encoding=None):
        assert mode in {"r", "rt", "rb"}

        with self.hdfs_client.read(
            path_info.path, encoding=encoding
        ) as reader:
            yield reader.read()

    def walk_files(self, path_info, **kwargs):
        if not self.exists(path_info):
            return

        root = path_info.path
        dir_queue = deque([root])

        while dir_queue:
            for path, dirs, files in self.hdfs_client.walk(
                dir_queue.pop(), depth=kwargs.get("depth", 0)
            ):
                new_dirs = [os.path.join(path, dir_) for dir_ in dirs]
                dir_queue.extend(new_dirs)

                for file_ in files:
                    path = os.path.join(path, file_)
                    yield path_info.replace(path=path)

    def remove(self, path_info):
        if path_info.scheme != self.scheme:
            raise NotImplementedError

        self.hdfs_client.delete(path_info.path)

    def exists(self, path_info, use_dvcignore=True):
        status = self.hdfs_client.status(path_info.path, strict=False)
        return status is not None

    def get_file_hash(self, path_info):
        return self.hdfs_client.checksum(path_info.path)

    def _upload(
        self, from_file, to_info, name=None, no_progress_bar=False, **_kwargs
    ):
        with Tqdm(desc=name, disable=no_progress_bar, bytes=True) as pbar:
            self.hdfs_client.upload(
                to_info.path, from_file, progress=update_pbar(pbar)
            )

    def _download(
        self, from_info, to_file, name=None, no_progress_bar=False, **_kwargs
    ):
        with Tqdm(desc=name, disable=no_progress_bar, bytes=True) as pbar:
            self.hdfs_client.download(
                from_info.path, to_file, progress=update_pbar(pbar)
            )
