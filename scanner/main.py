import ftplib
from pathlib import Path
from abc import ABC
from os import getenv
import cv2
from pathlib import Path
from loguru import logger
from datetime import datetime
import traceback


def now_str() -> str:
    dt = datetime.now()
    return dt.strftime("%Y%m%d%m%H%S")

class FtpClient(ABC):
    def _connect(self):
        pass
    def _is_connected(self):
        pass
    def upload_file(self, local_path: str | Path,
                    remote_path: str | Path) -> None:
        pass
    def close(self):
        pass


class FtpClientImpl(FtpClient):
    """
    Simple FTP client wrapper that supports uploading binary files.
    """

    def __init__(self, host: str, user: str = "", passwd: str = "",
                 port: int = 21, timeout: int | None = None):
        self.host = host
        self.user = user
        self.passwd = passwd
        self.port = port
        self.timeout = timeout
        self._conn: ftplib.FTP | None = None

    def _connect(self) -> ftplib.FTP:
        if self._conn is None or not self._is_connected():
            self._conn = ftplib.FTP()
            if self.timeout is not None:
                self._conn.connect(host=self.host, port=self.port,
                                   timeout=self.timeout)
            else:
                self._conn.connect(host=self.host, port=self.port)
            self._conn.login(user=self.user, passwd=self.passwd)
        return self._conn

    def _is_connected(self) -> bool:
        try:
            if self._conn is None:
                return False
            # A NOOP command checks the connection without affecting state.
            self._conn.voidcmd("NOOP")
            return True
        except (ftplib.error_temp, ftplib.error_perm):
            return False

    def upload_file(self, local_path: str | Path,
                    remote_path: str | Path) -> None:
        """
        Upload a binary file to the FTP server.

        Parameters
        ----------
        local_path : str or pathlib.Path
            Path to the local image file.
        remote_path : str or pathlib.Path
            Destination path on the FTP server, including filename.
        """
        conn = self._connect()
        with open(local_path, "rb") as f:
            # Use STOR for binary upload. The rest of the path is handled by
            # the server's current working directory; use cwd if needed.
            conn.storbinary(f"STOR {remote_path}", f)

    def close(self) -> None:
        """Close the FTP connection."""
        if self._conn is not None:
            try:
                self._conn.quit()
            finally:
                self._conn = None

    # Context manager support
    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()




class CameraCapture:
    """
    OpenCVを使ってカメラから一度だけ画像をキャプチャするクラス。
    """

    def __init__(self, device: int = 0):
        """
        カメラデバイスを初期化。

        Parameters
        ----------
        device : int
            カメラデバイス番号（デフォルトは0）。
        """
        self.device = device

    def capture_once(self, save_path: str | Path) -> bool:
        """
        カメラから一度だけ画像をキャプチャして保存。

        Parameters
        ----------
        save_path : str or pathlib.Path
            保存先のファイルパス。

        Returns
        -------
        bool
            キャプチャが成功したかどうか。
        """
        cap = cv2.VideoCapture(self.device)
        if not cap.isOpened():
            raise RuntimeError(f"カメラデバイス {self.device} を開けません。")

        ret, frame = cap.read()
        if ret:
            logger.info(f"writing capture image to ${save_path} ...")
            cv2.imwrite(str(save_path), frame)
            logger.info(f"writing capture image done.")
        else:
            logger.error("couldn't capture image")

        cap.release()
        return ret


def main():
    host = getenv("FTP_SRV_HOST")
    userid = getenv("FTP_SRV_USERID")
    passwd = getenv("FTP_SRV_PASSWD")
    img_path = getenv("SCANNED_IMG_PATH")
    if host is None or userid is None or passwd is None or img_path is None:
        raise RuntimeError("necessary info for FTP is not available.")

    # STEP1. Capture the camera and save the image to SCANNED_IMG_PATH
    capture = CameraCapture()
    fname = f"{now_str()}.png"
    img_path_obj = Path(img_path) / fname
    success = capture.capture_once(str(img_path_obj))
    if not success:
        raise RuntimeError("画像のキャプチャに失敗しました。")

    # STEP2. FTP the scanned image binary to blob store

    try:
        logger.info(f"preparing FTP to {host}@{userid}...")
        ftp_cl:FtpClient = FtpClientImpl(host ,userid, passwd)
        ftp_cl._connect()
        if not ftp_cl._is_connected():
            raise RuntimeError("FTP connection not established")
        logger.info("FTP connection established. Uploading file ..")
        ftp_cl.upload_file(str(img_path_obj), f"incoming/{fname}")
        ftp_cl.close()
        logger.info(f"Uploading file to incoming/{fname} done.")
        logger.info("All operations succeeded.")
    except Exception as e:
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
