import streamlit as st
from docx import Document
from typing import List, Dict, Tuple
from google import genai
from pydantic import BaseModel, Field
from io import BytesIO


class AnswerKey(BaseModel):
    para_id: int = Field(..., description="Paragraph ID where the answer key is located")
    answer: str = Field(..., description="The extracted answer key text")


class AnswerKeys(BaseModel):
    answer_keys: List[AnswerKey] = Field(..., description="List of identified answer keys")


def get_document_content(file_path: str) -> Tuple[Document, List[Dict[str, str]]]:
    """
    Extracts text from a .docx file and returns a list of indexed paragraphs.
    """
    doc = Document(file_path)
    content = []
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if text:  # Skip empty lines to save tokens
            content.append({
                "para_id": i,
                "text": text
            })
    return doc, content

prompt = """
You are an expert at identifying answer keys in educational documents.
Given the following document content, identify the paragraphs containing questions, and their corresponding answer keys.
Output a list of objects with 'para_id' and 'answer' fields. The `para_id` corresponds to the index of the QUESTION in the exam paper, and the `answer` is the text of the answer key.
Some question may span multiple paragraphs, but the `para_id` for that answer should point to the beginning of the question.
Some answers may correpond to multiple questions, especially for multiple choice questions. In such cases, list each question's `para_id` separately with the corresponding answer to that question.
For questions that contain sub-questions, break down the answer for each sub-question and list the `para_id` of each sub-question.
"""


def identify_answer_keys(doc_content: List[Dict[str, str]]) -> AnswerKeys:
    client = genai.Client(api_key=st.secrets["GENAI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt + "\nDocument Content:\n" + str(doc_content),
        config={
            "response_mime_type": "application/json",
            "response_json_schema": AnswerKeys.model_json_schema(),
        }
    )
    return AnswerKeys.model_validate_json(response.text)


def add_comments(doc: Document, answer_keys: AnswerKeys):
    for answer_key in answer_keys.answer_keys:
        paragraph = doc.paragraphs[answer_key.para_id]
        doc.add_comment(paragraph.runs, answer_key.answer, author="ChemistryAI")
    return doc


def main():
    st.title("文档答案标注工具")
    st.write("上传一个 .docx 文件以对其进行答案标注。")

    uploaded_file = st.file_uploader("上传一个 .docx 文件", type=["docx"])
    if uploaded_file:
        file_name = uploaded_file.name
        doc = Document(uploaded_file)
        _, doc_content = get_document_content(uploaded_file)

        with st.spinner("正在识别答案..."):
            answer_keys = identify_answer_keys(doc_content)

        with st.spinner("正在标注文档..."):
            annotated_doc = add_comments(doc, answer_keys)

        st.success("文档标注成功！")

        # Save the annotated document to a BytesIO object for download
        annotated_file = BytesIO()
        annotated_doc.save(annotated_file)
        annotated_file.seek(0)

        st.download_button(
            label="下载标注后的文档",
            data=annotated_file,
            file_name="annotated_" + file_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )


if __name__ == "__main__":
    main()
