# install the project and dependencies
cd pdf-translator-for-human
pip install -e .
pip install streamlit pymupdf openai 

# Start the Web Application
streamlit run app.py