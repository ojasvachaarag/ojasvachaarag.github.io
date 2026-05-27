#########################################################################################
#                                        IMPORTS                                        #
#########################################################################################

import os
import sys
import json
import torch

from time import time
from dotenv import load_dotenv
from torch import cuda

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline
)

from langchain import PromptTemplate
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.document_loaders import (
    PyPDFLoader,
    DirectoryLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.llms import HuggingFacePipeline

#########################################################################################
#                                   LOAD CONFIGURATION                                  #
#########################################################################################

load_dotenv()

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

#########################################################################################
#                                       CONSTANTS                                       #
#########################################################################################

DEVICE = "cuda" if cuda.is_available() else "cpu"

# Model paths
EMBEDDING_MODEL_PATH = config["models"]["embedding_model_path"]
LLM_MODEL_PATH = config["models"]["llm_model_path"]

# Documents
PDF_DIRECTORY_PATH = config["documents"]["pdf_directory_path"]

# Text splitter
CHUNK_SIZE = config["text_splitter"]["chunk_size"]
CHUNK_OVERLAP = config["text_splitter"]["chunk_overlap"]

# Generation params
TEMPERATURE = config["generation"]["temperature"]
MAX_NEW_TOK = config["generation"]["max_new_tokens"]
TOP_P = config["generation"]["top_p"]
DO_SAMPLE = config["generation"]["do_sample"]

# Retrieval
RETRIEVAL_K = config["retrieval"]["search_kwargs"]["k"]

# Logging
QA_LOG_FILE = config["logging"]["qa_log_file"]

# Prompt
SYSTEM_PROMPT = config["prompt"]["system_prompt"]

# Secrets
HF_TOKEN = os.getenv(config["secrets"]["hf_token_env"])

print(f"Using device: {DEVICE}")

#########################################################################################
#                                  FUNCTION DEFINITIONS                                 #
#########################################################################################

def check_local_model_paths():

    for p in [EMBEDDING_MODEL_PATH, LLM_MODEL_PATH]:

        if not os.path.isdir(p):

            raise FileNotFoundError(
                f"Local model path not found: {p}\n"
                f"Check your config.json paths."
            )

def load_documents():

    start = time()

    loader = DirectoryLoader(
        path=PDF_DIRECTORY_PATH,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
        recursive=True,
        show_progress=True
    )

    documents = loader.load()

    print(f"Loaded {len(documents)} documents.")
    print("Time taken: {:.2f}s".format(time() - start))

    return documents

def split_documents(documents):

    start = time()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    text_chunks = splitter.split_documents(documents)

    print(f"Split into {len(text_chunks)} text chunks.")
    print("Time taken: {:.2f}s".format(time() - start))

    return text_chunks

def create_vector_store(text_chunks):

    start = time()

    model_kwargs = {
        "device": DEVICE
    }

    encode_kwargs = {
        "normalize_embeddings": True
    }

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_PATH,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs,
    )

    vector_store = FAISS.from_documents(
        text_chunks,
        embeddings
    )

    print("Vector store created.")
    print("Time taken: {:.2f}s".format(time() - start))

    return vector_store

def _pick_dtype():

    if DEVICE == "cuda":

        if torch.cuda.is_bf16_supported():
            return torch.bfloat16

        return torch.float16

    return torch.float32

def init_llm():

    start = time()

    dtype = _pick_dtype()

    tokenizer = AutoTokenizer.from_pretrained(
        LLM_MODEL_PATH,
        use_fast=True,
        token=HF_TOKEN
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL_PATH,
        device_map="auto" if DEVICE == "cuda" else None,
        torch_dtype=dtype,
        token=HF_TOKEN
    )

    gen_pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=MAX_NEW_TOK,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        do_sample=DO_SAMPLE,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
        device=0 if DEVICE == "cuda" else -1,
    )

    llm = HuggingFacePipeline(
        pipeline=gen_pipe
    )

    print("LLM initialized.")
    print("Time taken: {:.2f}s".format(time() - start))

    return llm

def init_prompt():

    template = f"""
{SYSTEM_PROMPT}

Context:
{{context}}

Q: {{question}}

A:
""".strip()

    return PromptTemplate(
        template=template,
        input_variables=["context", "question"]
    )

def init_chain(llm, vector_store, prompt_template):

    retriever = vector_store.as_retriever(
        search_kwargs={"k": RETRIEVAL_K}
    )

    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={
            "prompt": prompt_template
        }
    )

def log_qa_to_file(question, answer):

    os.makedirs(
        os.path.dirname(QA_LOG_FILE),
        exist_ok=True
    )

    with open(QA_LOG_FILE, "a", encoding="utf-8") as f:

        f.write(
            f"Q: {question}\n"
            f"A: {answer}\n\n"
            f"{'-' * 80}\n\n"
        )

#########################################################################################
#                                        EXECUTION                                      #
#########################################################################################

if __name__ == "__main__":

    try:

        check_local_model_paths()

        documents = load_documents()

        if not documents:
            print("No PDFs found.")
            sys.exit(0)

        text_chunks = split_documents(documents)

        vector_store = create_vector_store(text_chunks)

        llm = init_llm()

        prompt_template = init_prompt()

        qa_chain = init_chain(
            llm,
            vector_store,
            prompt_template
        )

        while True:

            try:

                query = input(
                    "\nAsk a question (or type 'exit' to quit): "
                )

                if query.strip().lower() == "exit":
                    break

                response = qa_chain.run(query)

                print(f"\nSynaptIQ Answer:\n{response}")

                log_qa_to_file(query, response)

            except KeyboardInterrupt:

                print("\nInterrupted. Type 'exit' to quit.")

            except Exception as e:

                print(f"Error during QA: {e}")

    except KeyboardInterrupt:

        print("Exiting.")

    except Exception as e:

        print(f"Startup error: {e}")