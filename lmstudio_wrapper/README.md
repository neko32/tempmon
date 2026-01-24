# LM Studio Wrapper Web Server

Flaskベースのウェブサーバーです。Dockerコンテナとして稼働し、同じLAN内の別のホストからアクセス可能です。

## セットアップ

### Docker Composeを使用する場合

```bash
cd lmstudio_wrapper
docker-compose up -d
```

### Dockerのみを使用する場合

```bash
cd lmstudio_wrapper
docker build -t lmstudio-wrapper .
docker run -d -p 5000:5000 --name lmstudio-wrapper lmstudio-wrapper
```

## アクセス

- ローカルホスト: `http://localhost:5000`
- LAN内の他のホスト: `http://<サーバーのIPアドレス>:5000`

## API エンドポイント

- `GET /health` - ヘルスチェック
- `GET /api/v1/status` - サービスステータス取得
- `POST /api/v1/example` - サンプルエンドポイント

## 環境変数

- `PORT`: サーバーのポート番号（デフォルト: 5000）
- `HOST`: バインドするホスト（デフォルト: 0.0.0.0）
