from flask import Flask, request, send_file
from flask_cors import CORS  # Import CORS
import PyPDF2
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route("/", methods=["GET"])
def home():
    return "PDF Merger API is Running!"

@app.route("/merge", methods=["POST"])
def merge_pdfs():
    uploaded_files = request.files.getlist("pdfs")
    if len(uploaded_files) < 2:
        return "Upload at least two PDFs.", 400

    merger = PyPDF2.PdfMerger()
    for file in uploaded_files:
        merger.append(file)

    output_path = "merged_output.pdf"
    merger.write(output_path)
    merger.close()

    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
