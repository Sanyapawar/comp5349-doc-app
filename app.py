import os
import boto3
import psycopg2
import google.generativeai as genai
from flask import Flask, request, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
import PyPDF2
import io

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "comp5349-secret-key")

# ── Configuration ── loaded from environment variables (.env on EC2) ──────────
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")       # e.g. "comp5349-docs-yourname"

DB_HOST     = os.getenv("DB_HOST")                  # e.g. "xxx.rds.amazonaws.com"
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "docdb")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# ─────────────────────────────────────────────────────────────────────────────

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Configure S3 client (EC2 IAM role provides credentials automatically)
s3_client = boto3.client("s3", region_name=AWS_REGION)


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def extract_text_from_pdf(file_bytes):
    """Extract text from a PDF file bytes."""
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


def generate_summary(text):
    """Generate a concise summary using Google Gemini."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = (
        "Please provide a concise summary (3-5 sentences) of the following document:\n\n"
        + text[:10000]  # limit to avoid token overflow
    )
    response = model.generate_content(prompt)
    return response.text


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("No file selected.")
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))

    if not file.filename.lower().endswith(".pdf"):
        flash("Only PDF files are supported.")
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    file_bytes = file.read()

    # 1. Upload to S3
    s3_key = f"uploads/{filename}"
    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_bytes,
        ContentType="application/pdf",
    )

    # 2. Extract text and generate summary
    pdf_text = extract_text_from_pdf(file_bytes)
    if not pdf_text:
        flash("Could not extract text. Make sure it's a text-based PDF.")
        return redirect(url_for("index"))

    summary = generate_summary(pdf_text)

    # 3. Store metadata in RDS
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (filename, s3_key, summary) VALUES (%s, %s, %s)",
        (filename, s3_key, summary),
    )
    conn.commit()
    cur.close()
    conn.close()

    return render_template("result.html", filename=filename, s3_key=s3_key, summary=summary)


@app.route("/history", methods=["GET"])
def history():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT filename, s3_key, summary, uploaded_at FROM documents ORDER BY uploaded_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("history.html", documents=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
