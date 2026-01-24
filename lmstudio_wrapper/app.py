"""
Flask-based web server for LM Studio wrapper
"""
from flask import Flask, jsonify, request
import logging
from os import getenv
from ftplib import FTP
import lmstudio as lms
from datetime import datetime
import re
import tempfile
import os
import json
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
ftp_user = getenv('TEMPMON_FTP_USER')
ftp_passwd = getenv('TEMPMON_FTP_PASSWD')
ftp_host = getenv('TEMPMON_FTP_HOST')
llm_host = getenv('TEMPMON_LLM_SRV_HOST')
llm_port = getenv('TEMPMON_LLM_SRV_PORT')
model_name = getenv('TEMPMON_MODEL_NAME')
with open("llm_system_prompt.md", "r", encoding = 'utf-8') as f:
    system_prompt = f.read()
app = Flask(__name__)


def choose_nearest_one(file_names: list[str]) -> str:
    """
    FTPディレクトリ内のファイルリストから、現在時刻より過去で最も現在に近いファイルを選択する
    ファイル名は yyyymmdd_HHMMSS フォーマットであることを前提とする
    
    Args:
        file_names: ファイル名のリスト（yyyymmdd_HHMMSS形式）
        ftp: FTP接続オブジェクト（未使用だが互換性のため保持）
    
    Returns:
        現在時刻より過去で最も現在に近いファイル名
    """
    if not file_names:
        raise ValueError("File list is empty")
    
    if len(file_names) == 1:
        return file_names[0]
    
    # 現在時刻を取得
    now = datetime.now()
    
    # ファイル名から日時を抽出して、過去のファイルのみをフィルタリング
    past_files = []
    date_pattern = re.compile(r'(\d{8})_(\d{6})')  # yyyymmdd_HHMMSS
    
    for filename in file_names:
        # ファイル名から拡張子を除いた部分を取得
        name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # 日時パターンを検索
        match = date_pattern.search(name_without_ext)
        if match:
            date_str = match.group(1)  # yyyymmdd
            time_str = match.group(2)    # HHMMSS
            
            try:
                # 日時をパース
                file_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                
                # 現在時刻より過去のファイルのみを対象とする
                if file_datetime < now:
                    past_files.append((filename, file_datetime))
            except ValueError as e:
                logger.warning(f"Could not parse datetime from filename {filename}: {str(e)}")
                continue
    
    if not past_files:
        raise ValueError("No valid past files found in the list")
    
    # 日時でソート（新しい順）
    past_files.sort(key=lambda x: x[1], reverse=True)
    
    # 最も現在に近い（最新の）ファイルを返す
    chosen_file = past_files[0][0]
    chosen_datetime = past_files[0][1]
    logger.info(f"Chosen file: {chosen_file} (datetime: {chosen_datetime.strftime('%Y-%m-%d %H:%M:%S')}) from {len(file_names)} files")
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

            try:
                nearest_one = choose_nearest_one(file_list)
                logger.info(f"chosen file to process is {nearest_one}")

                # 一時ディレクトリを作成
                temp_dir = tempfile.mkdtemp(prefix='tempmon_')
                logger.info(f"Created temporary directory: {temp_dir}")
                
                # FTPからファイルをダウンロード
                local_file_path = os.path.join(temp_dir, nearest_one)
                logger.info(f"Downloading {nearest_one} to {local_file_path}")
                
                with open(local_file_path, 'wb') as local_file:
                    ftp.retrbinary(f'RETR {nearest_one}', local_file.write)
                
                logger.info(f"Successfully downloaded {nearest_one} to {local_file_path}")

                with lms.Client(api_host = f"{llm_host}:{llm_port}") as lms_cl:
                    image_handle = lms_cl.prepare_image(local_file_path)
                    # llmはプロパティで、model()メソッドでモデルを取得
                    model = lms_cl.llm.model(model_name) if model_name else lms_cl.llm.model()
                    # Chatはhistoryモジュールから直接インポートして使用
                    chat = lms.Chat()
                    chat.add_system_prompt(system_prompt)
                    chat.add_user_message("analyze the image and extract the data", images=[image_handle])
                    logger.info(f"sending request to {llm_host}:{llm_port} with model: {model_name}..")
                    prediction = model.respond(chat)
                    logger.info("got a prediction result.")
                    pred_result = prediction.content.replace("```json", "").replace("```", "").strip()

                # prediction.contentはJSON文字列なので、パースして返す
                logger.info(f"Prediction content: {pred_result}")
                try:
                    parsed_data = json.loads(pred_result)
                    
                    # 処理に成功したファイルはtempdirとFTPサイトからdelete
                    try:
                        # 一時ディレクトリとその中のファイルを削除
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                            logger.info(f"Deleted temporary directory: {temp_dir}")
                        
                        # FTPサイトからファイルを削除
                        ftp.delete(nearest_one)
                        logger.info(f"Deleted file from FTP server: {nearest_one}")
                    except Exception as delete_error:
                        logger.warning(f"Failed to delete files: {str(delete_error)}")
                        # 削除に失敗しても処理は続行
                    
                    return jsonify({
                        'status': 'success',
                        'data': parsed_data
                    }), 200
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to parse JSON from prediction.content: {str(je)}")
                    # JSONパースに失敗した場合は、処理失敗（ファイルは削除しない）
                    return jsonify({
                        'status': 'error',
                        'message': str(je)
                    }), 500

            except ValueError as ve:
                raise Exception(ve)
            
    except Exception as e:
        logger.error(f"Processing error occured: {str(e)}")
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
