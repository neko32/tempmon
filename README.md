# tempmon

**Temperature monitoring and alerting.**

This README describes the project layout and how to run the scanner with Docker.

---

## What this project does

- **Scanner (camera)**  
  Captures images with a Raspberry Pi camera (`rpicam-jpeg`), saves them locally, uploads to FTP, and can send data to n8n analysis flows.
- **Temperature**  
  Designed to capture images of thermometers (not sensors) and pass them into analysis flows. See `docs/system.drawio.svg` for the system diagram.

---

## Repository layout

| Path                   | Description                                                                                                                                                                 |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **scanner/**           | Main logic for camera capture, FTP upload, and n8n integration. `main.py` is for scheduled runs; `server.py` is an HTTP server that captures and returns a JPEG on request. |
| **lmstudio_wrapper/**  | Flask web API wrapping LM Studio (LLM). See `lmstudio_wrapper/README.md` for details.                                                                                       |
| **docs/**              | System diagram (`system.drawio.svg`) and other docs.                                                                                                                        |
| **docker-compose.yml** | Defines the Webcam Scanner container and how to run it.                                                                                                                     |

---

## Quick start (run the scanner with Docker)

1. Set environment variables:
   - `FTP_SRV_HOST`, `FTP_SRV_USERID`, `FTP_SRV_PASSWD` — FTP server connection.
   - `SCANNED_IMG_PATH` is set to `/app/scans` inside the container by default in the compose file; you can leave it as-is unless you change the `environment` section.
2. From the repo root, run:

   ```bash
   docker-compose up --build
   ```

3. The container mounts `/dev/video0` for camera access.  
   On WSL2 with a USB camera, you may need to attach the device (e.g. with usbipd-win). To test logic without a camera, you can comment out the `devices` section in `docker-compose.yml`.

Captured images are written to `./scans` by default.

---

## Environment variables (scanner)

| Variable                        | Description                                                  |
| ------------------------------- | ------------------------------------------------------------ |
| `SCANNED_IMG_PATH`              | Directory where captured images are saved (required).        |
| `FTP_SRV_HOST`                  | FTP host (default: `localhost`).                             |
| `FTP_SRV_USERID`                | FTP user (default: `user`).                                  |
| `FTP_SRV_PASSWD`                | FTP password (default: `password`).                          |
| `TEMPMON_IS_TEST`               | Use test n8n instance (default: `True`).                     |
| `N8N_INTEGRATION_FLAG`          | Whether to POST to the n8n analysis flow (default: `False`). |
| `N8N_LIVE_SRV` / `N8N_TEST_SRV` | Base URLs for n8n webhooks (live and test).                  |

---

## License

See `LICENSE`.
