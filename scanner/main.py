import ftplib
from pathlib import Path
from abc import ABC
from os import getenv
import cv2
from pathlib import Path
from loguru import logger
from datetime import datetime
import traceback
import subprocess
import requests
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url


def now_str() -> str:
    dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")

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

class CloudinaryClient:
    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )
    def upload_file(self, local_path: str | Path) -> str:
        resp = cloudinary.uploader.upload(local_path, unique_filename=True, overwrite=True)
        return resp["secure_url"]

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

def str_to_bool(s: str) -> bool:
    true_set = {"y", "yes", "t", "true", "on", "1"}
    false_set = {"n", "no", "f", "false", "off", "0"}

    s_lower = s.strip().lower()
    if s_lower in true_set:
        return True
    elif s_lower in false_set:
        return False
    else:
        raise ValueError(f"Invalid boolean string: {s}")

def main():
    ftp_host = getenv("FTP_SRV_HOST")
    ftp_userid = getenv("FTP_SRV_USERID")
    ftp_passwd = getenv("FTP_SRV_PASSWD")
    img_path = getenv("SCANNED_IMG_PATH")
    n8n_live_host = getenv("N8N_LIVE_SRV")
    n8n_test_host = getenv("N8N_TEST_SRV")
    cloudinary_cloud_name = getenv("CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key = getenv("CLOUDINARY_API_KEY")
    cloudinary_api_secret = getenv("CLOUDINARY_API_SECRET")
    
    if ftp_host is None or ftp_userid is None or ftp_passwd is None or img_path is None:
        raise RuntimeError("necessary info for FTP is not available.")

    if cloudinary_cloud_name is None or cloudinary_api_key is None or cloudinary_api_secret is None:
        raise RuntimeError("necessary info for Cloudinary is not available.")

    is_test_t = getenv("TEMPMON_IS_TEST")
    if is_test_t is None:
        is_test = True
    else:
        is_test = str_to_bool(is_test_t)

    tempmon_n2n_webhook = f"{n8n_test_host}:5678/webhook-test/analysis-flow" if is_test else f"{n8n_live_host}:5678/webhook/analysis_flow"

    n8n_integ_t = getenv("N8N_INTEGRATION_FLAG")
    if n8n_integ_t is None:
        n8n_integ = False
    else:
        n8n_integ = str_to_bool(n8n_integ_t)
    

    # STEP1. Capture the camera and save the image to SCANNED_IMG_PATH
    fname = f"{now_str()}.jpeg"
    img_path_obj = Path(img_path) / fname
    try:
        rez = subprocess.run(
            ["rpicam-jpeg", "-o", str(img_path_obj)],
            check = True
        )
    except Exception as e:
        raise RuntimeError(e)

    # STEP2. FTP the scanned image binary to blob store

    try:
        logger.info(f"preparing FTP to {ftp_host}@{ftp_userid}...")
        ftp_cl:FtpClient = FtpClientImpl(ftp_host ,ftp_userid, ftp_passwd)
        ftp_cl._connect()
        if not ftp_cl._is_connected():
            raise RuntimeError("FTP connection not established")
        logger.info("FTP connection established. Uploading file ..")
        ftp_cl.upload_file(str(img_path_obj), f"tempmon_incoming/{fname}")
        ftp_cl.upload_file(str(img_path_obj), f"tempmon_keep/{fname}")
        ftp_cl.close()
        logger.info(f"Uploading file to tempmon_incoming/{fname} done.")
    except Exception as e:
        logger.error(traceback.format_exc())

    # STEP3. Upload the image to Cloudinary
    try:
        logger.info(f"Uploading file to Cloudinary...")
        cloudinary_cl:CloudinaryClient = CloudinaryClient(cloudinary_cloud_name, cloudinary_api_key, cloudinary_api_secret)
        url = cloudinary_cl.upload_file(str(img_path_obj))
        logger.info(f"Uploading file to Cloudinary done. URL: {url}")
    except Exception as e:
        logger.error(traceback.format_exc())

    # 3. fire & forget N8N analysis flow if integration flag is ON
    if n8n_integ:
        # tempmon_n2n_webhookにHTTP POSTリクエストを送信
        try:
            logger.info(f"Sending POST request to {tempmon_n2n_webhook}...")
            response = requests.post(
                tempmon_n2n_webhook,
                json={"filename": fname, "image_path": str(img_path_obj), "cloudinary_url": url},
                headers={'Content-Type': 'application/json'},
                timeout=60
            )
            logger.info(f"HTTP POST response code: {response.status_code}")
            logger.info(f"HTTP POST response headers: {dict(response.headers)}")
            logger.info(f"HTTP POST response content: {response.text}")
            if response.status_code == 405:
                logger.error(f"405 Method Not Allowed - n8nのwebhookがPOSTメソッドを受け付けていません。URLを確認してください: {tempmon_n2n_webhook}")
        except Exception as e:
            logger.error(f"Failed to send POST request to {tempmon_n2n_webhook}: {str(e)}")
            logger.error(traceback.format_exc())
    else:
        logger.info("N8N integration is OFF. Skipping N8N analysis flow.")

    

    logger.info("All operations succeeded.")
    


if __name__ == "__main__":
    main()
