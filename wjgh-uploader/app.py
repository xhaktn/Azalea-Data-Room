from flask import Flask, request, render_template, jsonify
import os
import uuid
import boto3
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask_cors import CORS

# ===== 0) 환경 변수 로드 =====
load_dotenv()

# ===== 1) Flask 앱 =====
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ===== 2) MinIO(S3) 클라이언트 =====
s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
    region_name=os.getenv("S3_REGION")
)
BUCKET = os.getenv("S3_BUCKET")

# ===== 3) 라우트 =====
@app.route("/")
def index():
    # 선택사항: 템플릿 테스트 페이지
    # templates/index.html 이 있으면 렌더링, 없으면 간단 응답
    try:
        return render_template("index.html")
    except Exception:
        return "Flask is running."

# --- A) 업로드: /api/upload (프론트에서 사용)
@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "empty filename"}), 400

    safe_name = secure_filename(f.filename)
    file_id = str(uuid.uuid4())
    key = f"uploads/{file_id}/{safe_name}"

    # ContentType 유지해서 업로드
    s3.upload_fileobj(
        f, BUCKET, key,
        ExtraArgs={"ContentType": f.mimetype or "application/octet-stream"}
    )

    # 사이즈 확인
    head = s3.head_object(Bucket=BUCKET, Key=key)
    size = head.get("ContentLength", None)

    return jsonify({
        "fileId": file_id,
        "filename": safe_name,
        "key": key,
        "size": size
    })

# --- (선택) /upload: 예전 폼 전송과 호환용
@app.route("/upload", methods=["POST"])
def upload_compat():
    # 기존 index.html 폼 전송을 위한 호환 라우트
    if "file" not in request.files:
        return "No file uploaded", 400
    f = request.files["file"]
    if f.filename == "":
        return "Empty filename", 400
    safe_name = secure_filename(f.filename)
    key = f"uploads/legacy/{safe_name}"
    s3.upload_fileobj(f, BUCKET, key, ExtraArgs={"ContentType": f.mimetype or "application/octet-stream"})
    return f"✅ Uploaded '{safe_name}' successfully!"

# --- B) 다운로드용 서명 URL: /api/files?key=...
@app.route("/api/files", methods=["GET"])
def api_files_get():
    key = request.args.get("key")
    if not key:
        return jsonify({"error": "key required"}), 400
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=300  # 5분
    )
    return jsonify({"url": url})

# --- C) 첨부 삭제: /api/delete?key=...
@app.route("/api/delete", methods=["DELETE"])
def api_delete():
    key = request.args.get("key")
    if not key:
        return jsonify({"error": "key required"}), 400
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== 4) 실행 =====
if __name__ == "__main__":
    # 콘솔에 설정 확인용 로그(선택)
    print("[S3_ENDPOINT_URL]", os.getenv("S3_ENDPOINT_URL"))
    print("[S3_BUCKET]", BUCKET)
    app.run(debug=True)
