"""
Flask-based web server for LM Studio wrapper
"""
from flask import Flask, jsonify, request
import logging
from os import getenv
from ftplib import FTP
import lmstudio as lms

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
ftp_user = getenv('TEMPMON_FTP_USER')
ftp_passwd = getenv('TEMPMON_FTP_PASSWD')
ftp_host = getenv('TEMPMON_FTP_HOST')
app = Flask(__name__)


def choose_nearest_one(file_names: list[str], ftp: FTP) -> str:
    """
    FTPディレクトリ内のファイルリストから最新のファイルを選択する
    
    Args:
        file_names: ファイル名のリスト
        ftp: FTP接続オブジェクト
    
    Returns:
        最新のファイル名
    """
    if not file_names:
        raise ValueError("File list is empty")
    
    if len(file_names) == 1:
        return file_names[0]
    
    # ファイルの詳細情報（タイムスタンプ含む）を取得
    file_details = []
    for filename in file_names:
        try:
            # MDTMコマンドでファイルの修正日時を取得
            # 応答形式: "213 20260123201027" (YYYYMMDDHHmmss)
            response = ftp.sendcmd(f"MDTM {filename}")
            if response.startswith("213"):
                timestamp_str = response.split()[1]  # "20260123201027"
                file_details.append((filename, timestamp_str))
            else:
                # MDTMが失敗した場合は、ファイル名をそのまま使用（フォールバック）
                file_details.append((filename, ""))
        except Exception as e:
            logger.warning(f"Could not get timestamp for {filename}: {str(e)}")
            # タイムスタンプが取得できない場合は、ファイル名をそのまま使用
            file_details.append((filename, ""))
    
    # タイムスタンプでソート（新しい順）
    # タイムスタンプが空の場合は最後に配置
    file_details.sort(key=lambda x: x[1] if x[1] else "0", reverse=True)
    
    # 最新のファイルを返す
    chosen_file = file_details[0][0]
    logger.info(f"Chosen file: {chosen_file} (from {len(file_names)} files)")
    return chosen_file


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'lmstudio_wrapper'
    }), 200


@app.route('/api/v1/status', methods=['GET'])
def get_status():
    """Get service status"""

    for rule in app.url_map.iter_rules():
        logger.info(f"  {list(rule.methods)} {rule}")

    return jsonify({
        'status': 'running',
        'version': '1.0.0'
    }), 200

@app.route('/api/v1/analyze-image', methods=['POST'])
def analyze_image_endpoint():
    """Analyze image endpoint"""
    try:
        # FTP接続
        logger.info(f"Connecting to FTP server: {ftp_user}{ftp_host}")
        with FTP(ftp_host) as ftp:
            # ログイン
            ftp.login(user=ftp_user, passwd=ftp_passwd)
            logger.info("FTP login successful")
            ftp.sendcmd("OPTS UTF8 ON")
            
            # tempmon_incomingディレクトリに移動
            ftp.cwd('tempmon_incoming')
            logger.info("Changed to tempmon_incoming directory")
            
            # ファイルリストを取得して表示
            file_list = ftp.nlst()
            print("Files in tempmon_incoming:")
            for filename in file_list:
                print(f"  - {filename}")
            
            logger.info(f"Found {len(file_list)} files in tempmon_incoming")
            
            # Postmanで使えるように最低限のレスポンスを返す
            return jsonify({
                'status': 'success',
                'message': 'File list printed to console',
                'file_count': len(file_list)
            }), 200
            
    except Exception as e:
        logger.error(f"Error connecting to FTP or listing files: {str(e)}")
        print(f"Error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500



@app.route('/api/v1/example', methods=['POST'])
def example_endpoint():
    """Example POST endpoint"""
    try:
        data = request.get_json()
        logger.info(f"Received request: {data}")
        
        return jsonify({
            'message': 'Request received',
            'data': data
        }), 200
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """404エラーハンドラー - デバッグ用"""
    logger.warning(f"404 error: {request.method} {request.path}")
    # 登録されているルートを取得
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    
    return jsonify({
        'error': 'Not Found',
        'path': request.path,
        'method': request.method,
        'available_routes': routes
    }), 404


if __name__ == '__main__':
    # Listen on all interfaces (0.0.0.0) to accept connections from LAN
    # Use port 5000 by default, can be overridden via environment variable
    import os
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Starting Flask server on {host}:{port}")
    # 登録されているルートをログに出力
    logger.info("Registered routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"  {list(rule.methods)} {rule}")
    app.run(host=host, port=port, debug=True)
